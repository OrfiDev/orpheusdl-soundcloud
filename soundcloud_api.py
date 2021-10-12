from utils.utils import create_requests_session


class SoundCloudWebAPI:
    def __init__(self, access_token, exception):
        self.api_base = 'https://api-v2.soundcloud.com/'
        self.access_token = access_token
        self.exception = exception
        self.s = create_requests_session()

    def _get(self, url, params = {}):
        r = self.s.get(f'{self.api_base}{url}', params=params, headers={"Authorization": "OAuth " + self.access_token})
        if r.status_code not in [200, 201, 202]: raise self.exception(f'{r.status_code!s}: {r.text}')
        return r.json()

    def get_track_download(self, track_id):
        return self._get(f'tracks/{track_id}/download')['redirectUri']
    
    def get_track_stream_link(self, file_url, access_token): # Why does strip/lstrip not work here...?
        return self._get(file_url.split('https://api-v2.soundcloud.com/')[1], {'track_authorization': access_token})['url']

    def resolve_url(self, url):
        return self._get('resolve', {'url': url})

    def search(self, query_type, query, limit = 10):
        return self._get('search/' + query_type, {'limit': limit, 'top_results': 'v2', 'q': query})
    
    def get_user_albums_tracks(self, user_id):
        user_albums = self._get(f'users/{user_id}/albums', {'limit': 1000})
        album_data = {i['id']:i for i in user_albums['collection']}
        user_tracks = self._get(f'users/{user_id}/tracks', {'limit': 1000})
        track_data = {i['id']:i for i in user_tracks['collection']}
        return album_data, track_data
    
    def get_tracks_from_tracklist(self, track_data): # WHY?! Only the web player's api-v2 needs this garbage, not api or api-mobile
        tracks_to_get = [str(i['id']) for i in track_data if 'streamable' not in i]
        tracks_to_get_chunked = [tracks_to_get[i:i + 50] for i in range(0, len(tracks_to_get), 50)]
        new_track_data = {j['id']: j for j in sum([self._get('tracks', {'ids': ','.join(i)}) for i in tracks_to_get_chunked], [])}
        return {i['id']: (i if 'streamable' in i else new_track_data[i['id']]) for i in track_data}