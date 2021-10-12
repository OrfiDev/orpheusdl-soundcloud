import ffmpeg

from utils.models import *
from utils.utils import create_temp_filename, download_to_temp, silentremove
from .soundcloud_api import SoundCloudWebAPI


module_information = ModuleInformation(
    service_name = 'SoundCloud',
    module_supported_modes = ModuleModes.download,
    session_settings = {'web_access_token': '', 'artist_download_ignore_tracks_in_albums': True},
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
        
        self.dont_redownload_tracks = settings['artist_download_ignore_tracks_in_albums']
        self.already_downloaded = []
    
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
            qt, mode = 'user', 'artist'
        elif query_type is DownloadTypeEnum.playlist:
            qt, mode = 'playlist', 'playlist'
        elif query_type is DownloadTypeEnum.album:
            qt, mode = 'playlist', 'album'
        elif query_type is DownloadTypeEnum.track:
            qt, mode = 'track', 'track'
        else:
            raise self.exception(f'Query type {query_type.name} is unsupported')
        results = self.websession.search(qt+'s', query, limit*4 if qt == 'playlist' else limit)
        
        search_results, i = [], 0
        for result in results['collection']:
            if qt != 'playlist' or (qt == 'playlist' and ((result['is_album'] and mode == 'album') or (not result['is_album'] and mode == 'playlist'))):
                id_ = result['id']
                search_results.append(SearchResult(
                    result_id = id_,
                    name = result['title'] if qt != 'user' else result['username'],
                    artists = [result['user']['username']] if qt != 'user' else None,
                    extra_kwargs = {'data': {id_: result}}
                ))
                i += 1
            if i >= limit:
                break
    
        return search_results

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

    def get_track_info(self, track_id, quality_tier: QualityEnum, codec_options: CodecOptions, data, ignore=False):
        track_data = data[track_id]
        metadata = track_data.get('publisher_metadata')
        metadata = metadata if metadata else {}
        file_url, codec = None, None
        error = 'Already downloaded in album' if track_id in self.already_downloaded and ignore else None
        self.already_downloaded.append(track_id) if self.dont_redownload_tracks else []

        file_url, download_url, codec = None, None, CodecEnum.AAC
        if track_data['downloadable']:
            download_url = self.websession.get_track_download(track_id)
            codec = CodecEnum[self.websession.s.head(download_url).headers['Content-Type'].split('/')[1].replace('mpeg', 'mp3').replace('ogg', 'vorbis').upper()]
        elif track_data['streamable']:
            for i in track_data['media']['transcodings']: # TODO: add support for lower quality tiers
                if i['format']['protocol'] == 'progressive':
                    file_url = i['url']
                    codec = CodecEnum[i['preset'].split('_')[0].upper()]
                    break
            else:
                error = 'Track not streamable'
        else:
            error = 'Track not streamable'
        
        tags = Tags(
            genres = [track_data['genre'].split('/')] if 'genre' in track_data else None,
            composer = metadata.get('writer_composer'),
            copyright = metadata.get('p_line'),
            upc = metadata.get('upc_or_ean'),
            isrc = metadata.get('isrc')
        )

        return TrackInfo(
            name = track_data['title'],
            album = metadata.get('album_title'),
            album_id = '',
            artists = (metadata['artist'] if 'artist' in metadata else track_data['user']['username']).replace(' x ', ', ').split(', '),
            artist_id = '' if 'artist' in metadata else track_data['user']['permalink'],
            download_extra_kwargs = {'track_url': file_url, 'download_url': download_url, 'codec': codec, 'track_authorization': track_data['track_authorization']},
            codec = codec,
            sample_rate = 48,
            release_year = self.get_release_year(track_data),
            cover_url = track_data['artwork_url'].replace('-large', '-original'), # format doesn't work here?
            tags = tags,
            explicit = metadata.get('explicit'),
            error = error
        )
    
    def get_album_info(self, album_id, data):
        playlist_data = data[album_id]
        playlist_tracks = self.websession.get_tracks_from_tracklist(playlist_data['tracks'])
        return AlbumInfo(
            name = playlist_data['title'],
            artist = playlist_data['user']['username'],
            artist_id = playlist_data['user']['permalink'],
            cover_url = playlist_data['artwork_url'].replace('-large', '-original') if playlist_data['artwork_url'] else None,
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
            cover_url = playlist_data['artwork_url'].replace('-large', '-original') if playlist_data['artwork_url'] else None,
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
            track_extra_kwargs = {'data': track_data, 'ignore': True}
        )