from utils.utils import create_requests_session


class SoundCloudAPI:
    def __init__(self, access_token, exception):
        self.api_base = 'https://api-mobile.soundcloud.com/'
        self.access_token = access_token
        self.exception = exception
        self.s = create_requests_session()

    def _get(self, url, params = {}):
        r = self.s.get(f'{self.api_base}{url}', params=params, headers={"Authorization": "OAuth " + self.access_token})
        if r.status_code not in [200, 201, 202]:
            raise self.exception(f'{r.status_code!s}: {r.text}')
        return r.json()

    def resolve_url(self, url):
        return self._get('resolve', {'identifier': url})

    def search(self, query_type, query, limit = 10):
        return self._get('search/' + query_type, {'limit': limit, 'top_results': 'v2', 'q': query})

    def get_playlist(self, playlist_id):
        playlist_data = self._get(f'playlists/soundcloud:playlists:{playlist_id}/info', {'limit': 1000})
        tracks, cache_data = [], {'track': {}}
        for i in playlist_data['tracks']['collection']:
            track_id = i['urn'].split(':')[-1]
            tracks.append(track_id)
            cache_data[track_id] = i

        return playlist_data['playlist'], tracks, cache_data
    
    def get_user_albums_tracks(self, user_id):
        user_albums = self._get(f'users/soundcloud:users:{user_id}/albums/posted', {'limit': 1000})
        albums = [i['target_urn'].split(':')[-1] for i in user_albums['collection']]
        
        user_tracks = self._get(f'users/soundcloud:users:{user_id}/tracks/posted', {'limit': 1000})
        tracks, cache_data = [], {'track': {}}
        for i in user_tracks['collection']:
            track_id = i['target_urn'].split(':')[-1]
            tracks.append(track_id)
            cache_data[track_id] = i['track']
        
        return albums, tracks, cache_data