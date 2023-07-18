from azure.identity import DefaultAzureCredential
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
        file_content = self.download_file_from_data_lake(self.document_path, file_name)
        return file_content.decode('utf-8') if file_content else None
      
