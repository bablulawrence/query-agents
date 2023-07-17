import openai
import re
import os
import logging
import sys
from logging import StreamHandler

import json
from tenacity import retry, wait_random_exponential, stop_after_attempt  
from azure.core.credentials import AzureKeyCredential  
from azure.search.documents import SearchClient  
from azure.search.documents.indexes import SearchIndexClient  
from azure.search.documents.models import Vector  
from azure.search.documents.indexes.models import (  
    SearchIndex,  
    SearchField,  
    SearchFieldDataType,  
    SimpleField,  
    SearchableField,  
    SearchIndex,  
    SemanticConfiguration,  
    PrioritizedFields,  
    SemanticField,  
    SearchField,  
    SemanticSettings,  
    VectorSearch,  
    VectorSearchAlgorithmConfiguration,  
)  

# Configure environment variables  
az_search_service_endpoint = os.environ["AZURE_SEARCH_SERVICE_ENDPOINT"]
az_search_index_name = os.environ["AZURE_SEARCH_INDEX_NAME"]
az_search_credential = AzureKeyCredential(os.environ["AZURE_SEARCH_ADMIN_KEY"])

openai.api_type = os.environ['OPENAI_API_TYPE']
openai.api_base = os.environ["OPENAI_API_EMBEDDINGS_BASE"]
openai.api_key = os.environ['OPENAI_API_EMBEDDINGS_KEY']
openai.api_version = os.environ["OPENAI_API_EMBEDDINGS_VERSION"]
embeddings_deploy_name = os.environ["OPENAI_API_EMBEDDINGS_DEPLOY"]

openai.api_type = os.environ['OPENAI_API_TYPE']
openai.api_key = os.environ['OPENAI_API_KEY']
openai.api_base = os.environ["OPENAI_API_BASE"]
openai.api_version = os.environ["OPENAI_API_VERSION"]
text_gen_deploy_name = os.environ["OPENAI_API_TEXT_GEN_DEPLOY"]

class LLMChat:
    def __init__(self, system_prompt="", debug=False):
        self.messages = []
        self.debug = False
        self.messages.append({"role": "system", "content": system_prompt})
    
    def __call__(self, message):
        self.messages.append({"role": "user", "content": message})
        result = self.run()
        self.messages.append({"role": "assistant", "content": result})
        return result

    @retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
    def generate_embeddings(text):
        response = openai.Embedding.create(input=text, engine=embeddings_deploy_name)
        embeddings = response['data'][0]['embedding']
        return embeddings

    def run(self, debug=False):        
        completion = openai.ChatCompletion.create(engine=text_gen_deploy_name, 
                                                  temperature=0,
                                                  messages=self.messages)
        if (self.debug):
            {"completion_tokens": 86, "prompt_tokens": 26, "total_tokens": 112}
            print(completion.usage)        
        return completion.choices[0].message.content

class QueryAgent(LLMChat):
    
    def __init__(self, 
                    translation_examples,
                    database_schema, 
                    language_reference, 
                    session_examples,
                    db_tools, 
                    language="Kusto Query Language",
                    max_tries=5, 
                    debug=False):
        super().__init__(self.__generat_system_prompt__(language, translation_examples, 
                                                        database_schema, language_reference, session_examples), debug)
        self.max_tries = max_tries
        self.db_tools = db_tools
        self.logger = logging.getLogger(__name__)

    def __generat_system_prompt__(language,
                                  translation_examples, 
                                  database_schema, 
                                  language_reference, 
                                  session_examples):
        delimiter='####'
        prompt=f"""As an expert in {language}, your task is to translate natural language question into {language} queries.
        The process will proceed through a series of steps in a loop until an accurate query is obtained.
        The input question will be delimitter by {delimiter}.

        To accomplish this task, you will utilize:

        1. Sample Translations: This helps to understand how input query can be translated into KQL for the specific database\
        your are querying: 
        {translation_examples}
        2. Database Schema Reference: This helps to determine the tables and columns that need to be used in the output query: 
        {database_schema}
        3. Language Reference: This helps to understand the syntax of the output query: 
        {language_reference}

        You will output the steps using the following format:

        Thought:  You will describe your thought process on how to translate the input query into KQL.
        OutputQuery:  You will generate the output query.
        WAITING:  You will return WAITING.

        Results: This is the result of the query execution(first few rows only) which will be provided to you in the next call;\
        You will not generate this yourself.

        You will analyze the results for errors and inaccuracies, if it is correct, you will generate final output\
        in the following format:
        Thought: Your thought process about the results. 
        FinalQuery: the latest output query generated. You will not include Results or OutputQuery in the final output.

        Here are some example sessions: 
        {session_examples}
        """.strip()

        return prompt

    def create_examples_search_index(examples_file):        

        index_client = SearchIndexClient(
            endpoint=az_search_service_endpoint, credential=az_search_credential)
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, sortable=True, filterable=True, facetable=True),
            SearchableField(name="InputQuery", type=SearchFieldDataType.String),
            SearchableField(name="OuputQuery", type=SearchFieldDataType.String),
            SearchField(name="InputQueryVector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        searchable=True, vector_search_dimensions=1536, vector_search_configuration="query-vector-config"),
            SearchField(name="OutputQueryVector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        searchable=True, vector_search_dimensions=1536, vector_search_configuration="query-vector-config"),
        ]

        vector_search = VectorSearch(
            algorithm_configurations=[
                VectorSearchAlgorithmConfiguration(
                    name="query-vector-config",
                    kind="hnsw",
                    hnsw_parameters={
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine"
                    }
                )
            ]
        )

        semantic_config = SemanticConfiguration(
            name="query-semantic-config",
            prioritized_fields=PrioritizedFields(
                title_field=SemanticField(field_name="OutputQuery"),
                prioritized_content_fields=[SemanticField(field_name="OuptutQuery")]
            )
        )

        # Create the semantic settings with the configuration
        semantic_settings = SemanticSettings(configurations=[semantic_config])

        # Create the search index with the semantic settings
        index = SearchIndex(name=az_search_index_name, fields=fields,
                            vector_search=vector_search, semantic_settings=semantic_settings)
        result = index_client.create_or_update_index(index)
        print(f' {result.name} created')

        with open(examples_file, 'r', encoding='utf-8') as file:
            examples = json.load(file)
        
        for item in examples:
            input_query = item['InputQuery']
            output_query = item['OutputQuery']
            item['InputQueryVector'] = super.generate_embeddings(input_query)
            item['OuputQueryVector'] = super.generate_embeddings(output_query)

        search_client = SearchClient(endpoint=az_search_service_endpoint, 
                             index_name=az_search_index_name, 
                             credential=az_search_credential)
        
        result = search_client.upload_documents(json.dumps(examples))  
        
        print(f"Uploaded {len(examples)} documents") 


    @retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
    def search_examples_index(self, query):
        search_client = SearchClient(endpoint=az_search_service_endpoint, 
                             index_name=az_search_index_name, 
                             credential=az_search_credential)        
        results = search_client.search(  
            search_text=None,  
            vector=self.generate_embeddings(query),
            top_k=3,  
            vector_fields="InputQueryVector",
            select=["InputQuery", "OutputQuery"],
        )  

        results = [{ 
                        "InputQuery": result["InputQuery"], 
                        "OutputQuery": result["OutputQuery"]
                    } for result in list(results)]
        # print(json.dumps(results))

    def extract_query(self, text):
        pattern_final = re.compile(r'FinalQuery:(.*?)(?:(?=\nOutputQuery:)|(?=$))', re.DOTALL)
        matches_final = pattern_final.findall(text)
        
        if matches_final:
            return 'Final', matches_final[0].strip()
        
        pattern_output = re.compile(r'OutputQuery:(.*?)(?:(?=\nWAITING)|(?=\nOutputQuery:)|(?=$))', re.DOTALL)
        matches_output = pattern_output.findall(text)

        return 'Output', matches_output[-1].strip() if matches_output else None    
    

    def query(self, input_query, sample_rows_num=5):
        next_prompt = input_query
        self.logger.info(next_prompt)
        for i in range(self.max_tries):
            llm_result = super().__call__(next_prompt)
            self.logger.info(llm_result)
            query_type, query_text = self.extract_query(llm_result)
            if query_type == 'Output':
                try: 
                    query_results=self.db_tools.execute_query(query_text)
                    next_prompt = f"Results: {query_results.head(sample_rows_num).to_csv()}"
                except Exception as e:
                    next_prompt = f"Results: {e}"
            else:
                return query_text