import pandas as pd
import os
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.exceptions import KustoServiceError
from azure.kusto.data.helpers import dataframe_from_result_table

class KQLTools:
    def __init__(self, cluster, database) -> None:
        aad_tenant_id = os.environ['AAD_TENANT_ID']
        aad_client_id = os.environ['AAD_CLIENT_ID']
        aad_client_secret = os.environ['AAD_CLIENT_SECRET']
        kscb = KustoConnectionStringBuilder.with_aad_application_key_authentication(cluster, 
                                                    aad_client_id,
                                                    aad_client_secret, 
                                                    aad_tenant_id)
        self.client = KustoClient(kscb)
        self.database = database

    def execute_query(self, query):
        response  = self.client.execute(self.database, query)
        result_df = dataframe_from_result_table(response.primary_results[0])
        return result_df
