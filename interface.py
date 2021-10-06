import ffmpeg

from utils.models import *
from utils.utils import create_temp_filename, download_to_temp, silentremove
from .soundcloud_api import SoundCloudAPI


module_information = ModuleInformation(
    service_name = 'SoundCloud',
    module_supported_modes = ModuleModes.download,
    flags = ModuleFlags.custom_url_parsing,
    session_settings = {'access_token': '', 'artist_download_ignore_tracks_in_albums': True},
    netlocation_constant = 'soundcloud',
    test_url = 'https://soundcloud.com/alanwalker/darkside-feat-tomine-harket-au'
)


class ModuleInterface:
    def __init__(self, module_controller: ModuleController):
        self.exception = module_controller.module_error
        settings = module_controller.module_settings
        self.session = SoundCloudAPI(settings['access_token'], module_controller.module_error)
        self.dont_redownload_tracks = settings['artist_download_ignore_tracks_in_albums']

        self.types = {'user': DownloadTypeEnum.artist, 'track': DownloadTypeEnum.track, 'playlist': DownloadTypeEnum.playlist, 'file_url': ''}
        self.caches = {i:{} for i in self.types.keys()}
        self.already_downloaded = []

    def custom_url_parse(self, link):
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

    def search(self, query_type: DownloadTypeEnum, query, tags: Tags = None, limit = 10):
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

    def get_track_tempdir(self, track_id): # Done like this since the header is slightly broken? Not sure why
        track_url, codec = self.caches['file_url'][track_id]
        extension = codec_data[codec].container.name
        temp_location = download_to_temp(track_url, {"Authorization": "OAuth " + self.session.access_token}, extension)
        output_location = create_temp_filename() + '.' + extension
        try: # ffmpeg is used to correct the vorbis header, which is broken for some reason?
            ffmpeg.input(temp_location, hide_banner=None, y=None).output(output_location, acodec='copy', loglevel='error').run()
            silentremove(temp_location)
        except:
            print('FFmpeg is not installed or working! Using fallback, may have errors')
            output_location = temp_location
        return output_location

    def get_track_info(self, track_id, quality_tier: QualityEnum, codec_options: CodecOptions):
        track_data = self.caches['track'][track_id]
        file_url, codec = None, None
        error = 'Already downloaded in album' if track_id in self.already_downloaded else None
        self.already_downloaded.append(track_id) if self.dont_redownload_tracks else []

        # TODO: downloadable tracks should be done differently, not sure how
        for i in track_data['media']['transcodings']:
            if i['format']['protocol'] == 'progressive':
                file_url = i['url']
                codec = CodecEnum[i['preset'].split('_')[0].upper()]
                download_type = DownloadEnum.TEMP_FILE_PATH if codec is CodecEnum.AAC else DownloadEnum.URL
                self.caches['file_url'][track_id] = file_url, codec
                break
        else:
            error = 'Track not streamable'

        return TrackInfo(
            name = track_data['title'],
            album = '', # playlists replace albums on SoundCloud
            album_id = '',
            artists = [track_data['_embedded']['user']['username']],
            artist_id = track_data['_embedded']['user']['permalink'],
            download_type = download_type,
            file_url = file_url,
            file_url_headers = {"Authorization": "OAuth " + self.session.access_token},
            codec = codec,
            sample_rate = 48,
            release_year = int(track_data['published_at'].split('/')[0]),
            cover_url = track_data['artwork_url_template'].replace('{size}', 'original'), # format doesn't work here?
            tags = Tags( # TODO: replay_gain, replay_peak as they are provided, but they are in a weird format
                genres = [track_data['genre'].split('/')] if 'genre' in track_data else None
            ),
            error = error
        )
    
    def get_album_info(self, album_id):
        playlist_data, tracks, cache_data = self.session.get_playlist(album_id)
        self.caches['track'].update(cache_data)

        return AlbumInfo(
            name = playlist_data['title'],
            artist = playlist_data['_embedded']['user']['username'],
            artist_id = playlist_data['_embedded']['user']['permalink'],
            cover_url = playlist_data['artwork_url_template'].replace('{size}', 'original'),
            release_year = int(playlist_data['release_date'].split('-')[0]),
            tracks = tracks
        )
    
    def get_playlist_info(self, playlist_id):
        playlist_data, tracks, cache_data = self.session.get_playlist(playlist_id)
        self.caches['track'].update(cache_data)
        
        return PlaylistInfo(
            name = playlist_data['title'],
            creator = playlist_data['_embedded']['user']['username'],
            creator_id = playlist_data['_embedded']['user']['permalink'],
            cover_url = playlist_data['artwork_url_template'].replace('{size}', 'original'),
            release_year = int(playlist_data['release_date'].split('-')[0]),
            tracks = tracks
        )

    def get_artist_info(self, artist_id, get_credited_albums):
        albums, tracks, cache_data = self.session.get_user_albums_tracks(artist_id)
        self.caches['track'].update(cache_data)

        return ArtistInfo(
            name = self.caches['user'][artist_id]['username'],
            albums = albums,
            tracks = tracks
        )