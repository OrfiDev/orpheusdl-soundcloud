from utils.models import *
from .soundcloud_api import SoundCloudAPI


module_information = ModuleInformation(
    service_name = 'SoundCloud',
    module_supported_modes = ModuleModes.download,
    flags = ModuleFlags.custom_url_parsing,
    session_settings = {'access_token': ''},
    netlocation_constant = 'soundcloud',
    test_url = 'https://soundcloud.com/alanwalker/darkside-feat-tomine-harket-au'
)


class ModuleInterface:
    def __init__(self, module_controller: ModuleController):
        self.exception = module_controller.module_error
        settings = module_controller.module_settings
        self.session = SoundCloudAPI(settings['access_token'], module_controller.module_error)
        self.module_controller = module_controller

        self.types = {'user': DownloadTypeEnum.artist, 'track': DownloadTypeEnum.track, 'playlist': DownloadTypeEnum.playlist}
        self.caches = {i:{} for i in self.types.keys()}

    def custom_url_parse(self, link: str):
        results = self.session.resolve_url(link)
        for i in self.types.keys():
            if i in results:
                type_ = DownloadTypeEnum.album if i == 'playlist' and results[i]['is_album'] else self.types[i]
                id_ = results[i]['urn'].split(':')[-1]
                self.caches[i][id_] = results[i]
                break
        else:
            raise self.exception('URL is invalid')

        return type_, id_

    def search(self, query_type: DownloadTypeEnum, query: str, tags: Tags = None, limit: int = 10):
        if query_type is DownloadTypeEnum.artist:
            qt, mode = 'user', 'artist'
        elif query_type is DownloadTypeEnum.playlist:
            qt, mode = 'playlist', 'playlist'
        elif query_type is DownloadTypeEnum.album:
            qt, mode = 'playlist', 'album'
        elif query_type is DownloadTypeEnum.track:
            qt, mode = 'track', 'track'
        else:
            raise self.exception(f'Query type {query_type.name} is unsupported')
        results = self.session.search(qt+'s', query, limit*4 if qt == 'playlist' else limit)
        
        search_results, i = [], 0
        for result in results['collection']:
            if qt != 'playlist' or (qt == 'playlist' and ((result['is_album'] and mode == 'album') or (not result['is_album'] and mode == 'playlist'))):
                id_ = result['urn'].split(':')[-1]
                self.caches[qt][id_] = result
                search_results.append(SearchResult(
                    result_id = id_,
                    name = result['title'] if qt != 'user' else result['username'],
                    #artists = [f"{i['_embedded']['user']['first_name']} {i['_embedded']['user']['last_name']}"] if '_embedded' in i else None))
                    artists = [result['_embedded']['user']['username']] if qt != 'user' else None
                ))
                i += 1
            if i >= limit:
                break
    
        return search_results

    def get_track_info(self, track_id: str) -> TrackInfo:
        if track_id not in self.caches['track']:
            raise self.exception('Track not cached...?')
        
        track_data = self.caches['track'][track_id]
        file_url, codec = None, None
        for i in track_data['media']['transcodings']:
            if i['format']['protocol'] == 'progressive':
                file_url = i['url']
                codec = CodecEnum[i['preset'].split('_')[0].upper()]
                break
        else:
            raise self.exception('Track is not streamable')

        return TrackInfo(
            track_name = track_data['title'],
            album_id = '', # playlists replace albums on SoundCloud
            album_name = '',
            artist_name = track_data['_embedded']['user']['username'],
            artist_id = track_data['_embedded']['user']['permalink'],
            download_type = DownloadEnum.URL,
            file_url = file_url,
            file_url_headers = {"Authorization": "OAuth " + self.session.access_token},
            codec = codec,
            sample_rate = 48,
            cover_url = track_data['artwork_url_template'].replace('{size}', 'original'), # format doesn't work here?
            tags = Tags( # TODO: replay_gain, replay_peak as they are provided, but they are in a weird format
                title = track_data['title'],
                album = None,
                artist = track_data['_embedded']['user']['username'],
                date = track_data['published_at'].split('/')[0],
                genre = track_data['genre'].split('/') if 'genre' in track_data else None
            )
        )
    
    def get_album_info(self, album_id: str) -> AlbumInfo:
        playlist_data, tracks, cache_data = self.session.get_playlist(album_id)
        self.caches.update(cache_data)

        return AlbumInfo(
            album_name = playlist_data['title'],
            artist_name = playlist_data['_embedded']['user']['username'],
            artist_id = playlist_data['_embedded']['user']['permalink'],
            cover_url = playlist_data['artwork_url_template'].replace('{size}', 'original'),
            tracks = tracks
        )
    
    def get_playlist_info(self, playlist_id: str) -> PlaylistInfo:
        playlist_data, tracks, cache_data = self.session.get_playlist(playlist_id)
        self.caches.update(cache_data)
        
        return PlaylistInfo(
            playlist_name = playlist_data['title'],
            playlist_creator_name = playlist_data['_embedded']['user']['username'],
            playlist_creator_id = playlist_data['_embedded']['user']['permalink'],
            cover_url = playlist_data['artwork_url_template'].replace('{size}', 'original'),
            tracks = tracks
        )

    # def get_artist_info(self, artist_id: str) -> ArtistInfo: # TODO later somehow, since the whole system of using albums obviously doesn't work here
    #     artist_data, albums, cache_data = self.session.get_artist(artist_id)
    #     self.caches.update(cache_data)

    #     return ArtistInfo(
    #         artist_name = artist_data['username'],
    #         albums = albums
    #     )