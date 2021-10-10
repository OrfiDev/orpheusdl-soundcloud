import ffmpeg

from utils.models import *
from utils.utils import create_temp_filename, download_to_temp, silentremove
from .soundcloud_api import SoundCloudAPI


module_information = ModuleInformation(
    service_name = 'SoundCloud',
    module_supported_modes = ModuleModes.download,
    session_settings = {'access_token': '', 'artist_download_ignore_tracks_in_albums': True},
    netlocation_constant = 'soundcloud',
    test_url = 'https://soundcloud.com/alanwalker/darkside-feat-tomine-harket-au',
    url_decoding = ManualEnum.manual,
    login_behaviour = ManualEnum.manual
)


class ModuleInterface:
    def __init__(self, module_controller: ModuleController):
        self.exception = module_controller.module_error
        settings = module_controller.module_settings
        self.session = SoundCloudAPI(settings['access_token'], module_controller.module_error)
        
        self.dont_redownload_tracks = settings['artist_download_ignore_tracks_in_albums']
        self.already_downloaded = []

    def custom_url_parse(self, link):
        types_ = {'user': DownloadTypeEnum.artist, 'track': DownloadTypeEnum.track, 'playlist': DownloadTypeEnum.playlist}
        results = self.session.resolve_url(link)
        for i in types_.keys():
            if i in results:
                type_ = DownloadTypeEnum.album if i == 'playlist' and results[i]['is_album'] else types_[i]
                id_ = results[i]['urn'].split(':')[-1]
                break
        else:
            raise self.exception('URL is invalid')
        
        return MediaIdentification(
            media_type = type_,
            media_id = id_,
            extra_kwargs = {'data': {id_: results[i]}} if type_ == DownloadTypeEnum.track or type_ == DownloadTypeEnum.artist else {}
        )

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
                search_results.append(SearchResult(
                    result_id = id_,
                    name = result['title'] if qt != 'user' else result['username'],
                    #artists = [f"{i['_embedded']['user']['first_name']} {i['_embedded']['user']['last_name']}"] if '_embedded' in i else None))
                    artists = [result['_embedded']['user']['username']] if qt != 'user' else None,
                    extra_kwargs = {'data': {id_: result}} if mode == 'track' or mode == 'artist' else {},
                ))
                i += 1
            if i >= limit:
                break
    
        return search_results

    def get_track_download(self, track_url, codec):
        if codec == CodecEnum.AAC: # Done like this since the header is slightly broken? Not sure why
            extension = codec_data[codec].container.name
            temp_location = download_to_temp(track_url, {"Authorization": "OAuth " + self.session.access_token}, extension)
            output_location = create_temp_filename() + '.' + extension
            try: # ffmpeg is used to correct the vorbis header, which is broken for some reason?
                ffmpeg.input(temp_location, hide_banner=None, y=None).output(output_location, acodec='copy', loglevel='error').run()
                silentremove(temp_location)
            except:
                print('FFmpeg is not installed or working! Using fallback, may have errors')
                output_location = temp_location

            return TrackDownloadInfo(
                download_type = DownloadEnum.TEMP_FILE_PATH,
                temp_file_path = output_location
            )
        
        else:
            return TrackDownloadInfo(
                download_type = DownloadEnum.URL,
                file_url = track_url,
                file_url_headers = {"Authorization": "OAuth " + self.session.access_token}
            )

    def get_track_info(self, track_id, quality_tier: QualityEnum, codec_options: CodecOptions, data, ignore=False):
        track_data = data[track_id]
        file_url, codec = None, None
        error = 'Already downloaded in album' if track_id in self.already_downloaded and ignore else None
        self.already_downloaded.append(track_id) if self.dont_redownload_tracks else []

        # TODO: downloadable tracks should be done differently, not sure how
        # TODO: add support for lower quality tiers
        for i in track_data['media']['transcodings']:
            if i['format']['protocol'] == 'progressive':
                file_url = i['url']
                codec = CodecEnum[i['preset'].split('_')[0].upper()]
                break
        else:
            error = 'Track not streamable'

        return TrackInfo(
            name = track_data['title'],
            album = '', # playlists replace albums on SoundCloud
            album_id = '',
            artists = [track_data['_embedded']['user']['username']],
            artist_id = track_data['_embedded']['user']['permalink'],
            download_extra_kwargs = {'track_url': file_url, 'codec':codec},
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

        return AlbumInfo(
            name = playlist_data['title'],
            artist = playlist_data['_embedded']['user']['username'],
            artist_id = playlist_data['_embedded']['user']['permalink'],
            cover_url = playlist_data['artwork_url_template'].replace('{size}', 'original'),
            release_year = int(playlist_data['release_date'].split('-')[0]),
            tracks = tracks,
            track_extra_kwargs = {'data': cache_data}
        )
    
    def get_playlist_info(self, playlist_id):
        playlist_data, tracks, cache_data = self.session.get_playlist(playlist_id)
        
        return PlaylistInfo(
            name = playlist_data['title'],
            creator = playlist_data['_embedded']['user']['username'],
            creator_id = playlist_data['_embedded']['user']['permalink'],
            cover_url = playlist_data['artwork_url_template'].replace('{size}', 'original'),
            release_year = int(playlist_data['release_date'].split('-')[0]),
            tracks = tracks,
            track_extra_kwargs = {'data': cache_data}
        )

    def get_artist_info(self, artist_id, get_credited_albums, data):
        albums, tracks, cache_data = self.session.get_user_albums_tracks(artist_id)

        return ArtistInfo(
            name = data[artist_id]['username'],
            albums = albums,
            tracks = tracks,
            track_extra_kwargs = {'data': cache_data, 'ignore': True}
        )