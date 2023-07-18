import os
import azure.functions as func
from tools import KQLTools
from agents import QueryAgent, AzureSearchService, LLMChat

app = func.FunctionApp()

@app.function_name(name="echo")
@app.route(route="echo")
def main(req: func.HttpRequest) -> str:
    query = req.params.get("query")
    return f"This is your query, {query}!"

@app.function_name(name="KQLQueryAgent")
@app.route(route="kql")
def main(req: func.HttpRequest) -> str:
    input_query = req.params.get("query")
    storage_account = os.environ['ADLS_STORAGE_ACCOUNT']
    storage_container = os.environ['ADLS_STORAGE_CONTAINER']
    document_path = os.environ['ADLS_KUSTO_DOCUMENT_PATH']
    cluster = os.environ['ADLS_KUSTO_CLUSTER']
    database = os.environ['ADLS_KUSTO_DATABASE']
    
    kql_tools = KQLTools(cluster, 
                         database, 
                         storage_account, 
                         storage_container, 
                         document_path)
    
    documents = kql_tools.get_context_documents()

    azure_search_service = AzureSearchService()

    # Initialize the QueryAgent
    query_agent = QueryAgent(
        translation_examples=documents['translation_examples'],
        database_schema=documents['database_schema'],
        language_reference=documents['language_reference'],
        session_examples=documents['session_examples'],
        db_tools=kql_tools,
        azure_search_service=azure_search_service,
        language="Kusto Query Language",
        max_tries=3,
        debug=False
    )

    # Translate input query to KQL
    output_result = query_agent.query(input_query)
    print("Query result:", output_result)

    # print(documents)

    return output_result