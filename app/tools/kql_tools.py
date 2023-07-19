import pandas as pd
import os
import json
import logging
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.exceptions import KustoServiceError
from azure.kusto.data.helpers import dataframe_from_result_table
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.storage.filedatalake import DataLakeServiceClient

class DataLakeTools:
    def __init__(self, storage_account, storage_container, document_path) -> None:
        """
        Initialize KQLTools with Azure credentials and settings.
        """
        self.storage_account = storage_account
        self.storage_container = storage_container
        self.document_path = document_path

    def download_file_from_data_lake(self, folder_path, file_name):
        """
        Download file from Azure Data Lake.
        """
        file_path = f"{folder_path}/{file_name}"
        try:
            credential = DefaultAzureCredential()
            data_lake_service_client = DataLakeServiceClient(
                account_url=f"https://{self.storage_account}.dfs.core.windows.net",
                credential=credential
            )
            # logging.info(credential.get_token("https://storage.azure.com/.default"))
            file_system_client = data_lake_service_client.get_file_system_client(self.storage_container)
            file_client = file_system_client.get_file_client(file_path)

            download_stream = file_client.download_file()
            return download_stream.readall()
        except Exception as e:
            print(f"Failed to download file {file_path} from Data Lake: {e}")
            return None

    def get_decoded_file_content(self, file_name):
        """
        Download and decode file content.
        """
        file_content = self._download_file_from_data_lake(self.document_path, file_name)
        return file_content.decode('utf-8') if file_content else None

        
class KQLTools:
    """
    KQLTools is a class for handling operations related to Azure Data Lake and Kusto.
    """
    def __init__(self, cluster, database) -> None:
        """
        Initialize KQLTools with Azure credentials and settings.
        """
        aad_tenant_id = os.environ['AAD_TENANT_ID']
        aad_client_id = os.environ['AAD_CLIENT_ID']
        aad_client_secret = os.environ['AAD_CLIENT_SECRET']

        connection_string_builder = KustoConnectionStringBuilder.with_aad_application_key_authentication(
                                        cluster, 
                                        aad_client_id,
                                        aad_client_secret, 
                                        aad_tenant_id)
        self.client = KustoClient(connection_string_builder)
        self.database = database
          
    def execute_query(self, query):
        """
        Execute Kusto query.
        """
        try:
            response  = self.client.execute(self.database, query)
            result_df = dataframe_from_result_table(response.primary_results[0])
            return result_df
        except KustoServiceError as e:
            print(f"Kusto query failed: {e}")
            return None
