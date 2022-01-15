import ffmpeg

from utils.models import *
from utils.utils import create_temp_filename, download_to_temp, silentremove
from .soundcloud_api import SoundCloudWebAPI


module_information = ModuleInformation(
    service_name = 'SoundCloud',
    module_supported_modes = ModuleModes.download,
    session_settings = {'web_access_token': ''},
    netlocation_constant = 'soundcloud',
    test_url = 'https://soundcloud.com/alanwalker/darkside-feat-tomine-harket-au',
    url_decoding = ManualEnum.manual,
    login_behaviour = ManualEnum.manual
)


class ModuleInterface:
    def __init__(self, module_controller: ModuleController):
        self.exception = module_controller.module_error
        settings = module_controller.module_settings
        self.websession = SoundCloudWebAPI(settings['web_access_token'], module_controller.module_error)

        self.artists_split = lambda artists_string: artists_string.replace(' & ', ', ').replace(' and ', ', ').replace(' x ', ', ').split(', ') if ', ' in artists_string else [artists_string]
        self.artwork_url_format = lambda artwork_url: artwork_url.replace('-large', '-original') if artwork_url else None
    

    @staticmethod
    def get_release_year(data):
        release_date = ''
        if 'release_date' in data and data['release_date']:
            release_date = data['release_date']
        elif 'display_date' in data and data['display_date']:
            release_date = data['display_date']
        elif 'created_at' in data and data['created_at']:
            release_date = data['created_at']
        return int(release_date.split('-')[0])


    def custom_url_parse(self, link):
        types_ = {'user': DownloadTypeEnum.artist, 'track': DownloadTypeEnum.track, 'playlist': DownloadTypeEnum.playlist}
        result = self.websession.resolve_url(link)
        type_ = types_[result['kind']] if result['kind'] != 'playlist' or (result['kind'] == 'playlist' and not result['is_album']) else DownloadTypeEnum.album
        id_ = result['id']
        
        return MediaIdentification(
            media_type = type_,
            media_id = id_,
            extra_kwargs = {'data': {id_: result}}
        )


    def search(self, query_type: DownloadTypeEnum, query, tags: Tags = None, limit = 10):
        if query_type is DownloadTypeEnum.artist:
            qt = 'users'
        elif query_type is DownloadTypeEnum.playlist:
            qt = 'playlists_without_albums'
        elif query_type is DownloadTypeEnum.album:
            qt = 'albums'
        elif query_type is DownloadTypeEnum.track:
            qt = 'tracks'
        else:
            raise self.exception(f'Query type {query_type.name} is unsupported')
        results = self.websession.search(qt, query, limit)
        
        return [SearchResult(
            result_id = result['id'],
            name = result['title'] if qt != 'users' else result['username'],
            artists = self.artists_split(result['user']['username']) if qt != 'users' else None,
            extra_kwargs = {'data': {result['id'] : result}}
        ) for result in results['collection']]


    def get_track_download(self, track_url, download_url, codec, track_authorization):
        if not download_url: download_url = self.websession.get_track_stream_link(track_url, track_authorization)
        if codec == CodecEnum.AAC: # Done like this since the header is slightly broken? Not sure why
            extension = codec_data[codec].container.name
            temp_location = download_to_temp(download_url, {"Authorization": "OAuth " + self.websession.access_token}, extension)
            output_location = create_temp_filename() + '.' + extension
            try:
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
                file_url = download_url,
                file_url_headers = {"Authorization": "OAuth " + self.websession.access_token}
            )


    def get_track_info(self, track_id, quality_tier: QualityEnum, codec_options: CodecOptions, data={}):
        track_data = data[track_id] if track_id in data else self.websession._get('tracks/' + track_id)
        metadata = track_data.get('publisher_metadata', {})

        file_url, download_url, codec, error = None, None, CodecEnum.AAC, None
        if track_data['downloadable']:
            download_url = self.websession.get_track_download(track_id)
            codec = CodecEnum[self.websession.s.head(download_url).headers['Content-Type'].split('/')[1].replace('mpeg', 'mp3').replace('ogg', 'vorbis').upper()]
        elif track_data['streamable']:
            if track_data['media']['transcodings']:
                for i in track_data['media']['transcodings']: # TODO: add support for lower quality tiers
                    if i['format']['protocol'] == 'progressive':
                        file_url = i['url']
                        codec = CodecEnum[i['preset'].split('_')[0].upper()]
                        break
                else:
                    error = 'Track requires HLS, so it cannot be downloaded by this module until a later update'
            else:
                error = 'Track not streamable'
        else:
            error = 'Track not streamable'

        return TrackInfo(
            name = track_data['title'].split(' - ')[1] if ' - ' in track_data['title'] else track_data['title'],
            album = metadata.get('album_title'),
            album_id = '',
            artists = self.artists_split(metadata['artist'] if metadata.get('artist') else track_data['user']['username']),
            artist_id = '' if 'artist' in metadata else track_data['user']['permalink'],
            download_extra_kwargs = {'track_url': file_url, 'download_url': download_url, 'codec': codec, 'track_authorization': track_data['track_authorization']},
            codec = codec,
            sample_rate = 48,
            release_year = self.get_release_year(track_data),
            cover_url = self.artwork_url_format(track_data['artwork_url']),
            explicit = metadata.get('explicit'),
            error = error,
            tags =  Tags(
                genres = [track_data['genre'].split('/')] if 'genre' in track_data else None,
                composer = metadata.get('writer_composer'),
                copyright = metadata.get('p_line'),
                upc = metadata.get('upc_or_ean'),
                isrc = metadata.get('isrc')
            )
        )
    

    def get_album_info(self, album_id, data):
        playlist_data = data[album_id]
        playlist_tracks = self.websession.get_tracks_from_tracklist(playlist_data['tracks'])
        return AlbumInfo(
            name = playlist_data['title'],
            artist = playlist_data['user']['username'],
            artist_id = playlist_data['user']['permalink'],
            cover_url = self.artwork_url_format(playlist_data['artwork_url']),
            release_year = self.get_release_year(playlist_data),
            tracks = list(playlist_tracks.keys()),
            track_extra_kwargs = {'data': playlist_tracks}
        )
    

    def get_playlist_info(self, playlist_id, data):
        playlist_data = data[playlist_id]
        playlist_tracks = self.websession.get_tracks_from_tracklist(playlist_data['tracks'])
        return PlaylistInfo(
            name = playlist_data['title'],
            creator = playlist_data['user']['username'],
            creator_id = playlist_data['user']['permalink'],
            cover_url = self.artwork_url_format(playlist_data['artwork_url']),
            release_year = self.get_release_year(playlist_data),
            tracks = list(playlist_tracks.keys()),
            track_extra_kwargs = {'data': playlist_tracks}
        )


    def get_artist_info(self, artist_id, get_credited_albums, data):
        album_data, track_data = self.websession.get_user_albums_tracks(artist_id)
        return ArtistInfo(
            name = data[artist_id]['username'],
            albums = list(album_data.keys()),
            album_extra_kwargs = {'data': album_data},
            tracks = list(track_data.keys()),
            track_extra_kwargs = {'data': track_data}
        )
