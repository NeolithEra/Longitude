from carto.auth import APIKeyAuthClient
from carto.exceptions import CartoException
from carto.sql import BatchSQLClient, SQLClient

from ..common.query_response import LongitudeQueryResponse
from .base import DataSource, LongitudeQueryCannotBeExecutedException


class CartoDataSource(DataSource):
    SUBDOMAIN_URL_PATTERN = "https://%s.carto.com"
    ON_PREMISE_URL_PATTERN = "https://%s/user/%s"
    _default_config = {
        'api_version': 'v2',
        'uses_batch': False,
        'on_premise_domain': '',
        'api_key': '',
        'user': '',
        'cache': None
    }

    def __init__(self, config=None, cache_class=None):
        super().__init__(config, cache_class=cache_class)
        self._sql_client = None
        self._batch_client = None
        self.set_custom_query_default('do_post', False)
        self.set_custom_query_default('parse_json', True)
        self.set_custom_query_default('format', 'json')

    def setup(self):
        auth_client = APIKeyAuthClient(api_key=self.get_config('api_key'), base_url=self.base_url)
        self._sql_client = SQLClient(auth_client, api_version=self.get_config('api_version'))

        if self.get_config('uses_batch'):
            self._batch_client = BatchSQLClient(auth_client)
        super().setup()

    @property
    def base_url(self):
        user = self.get_config('user')
        on_premise_domain = self.get_config('on_premise_domain')
        if on_premise_domain:
            base_url = self.ON_PREMISE_URL_PATTERN % (on_premise_domain, user)
        else:
            base_url = self.SUBDOMAIN_URL_PATTERN % user
        return base_url

    @property
    def is_ready(self):
        if super().is_ready:
            sql_setup_ready = self._sql_client is not None
            batch_setup_ready = not self.get_config('uses_batch') or (self._batch_client is not None)
            is_ready = sql_setup_ready and batch_setup_ready and self.get_config('user') != ''
            return is_ready
        else:
            return False

    def execute_query(self, query_template, params, needs_commit, query_config, **opts):
        # TODO: Here we are parsing the parameters and taking responsability for it. We do not make any safe parsing as
        #  this will be used in a backend-to-backend context and we build our own queries.
        #  ---
        #  There is an open issue in CARTO about having separated parameters and binding them in the server:
        #  https://github.com/CartoDB/Geographica-Product-Coordination/issues/57
        formatted_query = query_template.format(**params)

        parse_json = query_config.custom['parse_json']
        do_post = query_config.custom['do_post']
        format_ = query_config.custom['format']
        try:
            return self._sql_client.send(formatted_query, parse_json=parse_json, do_post=do_post, format=format_)

        except CartoException as e:
            raise LongitudeQueryCannotBeExecutedException

    def parse_response(self, response):
        return LongitudeQueryResponse(
            rows=response['rows'],
            fields=response['fields'],
            profiling={
                'response_time': response['time'],
                'total_rows': response['total_rows']
            }
        )