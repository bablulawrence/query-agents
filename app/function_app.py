import os
import logging
import json
import azure.functions as func
from tools import KQLTools, DataLakeTools
from agents import QueryAgent, AzureSearchService, LLMChat

app = func.FunctionApp()

@app.function_name(name="echo")
@app.route(route="echo")
def main(req: func.HttpRequest) -> str:
    query = req.params.get("query")
    return f"This is your query, {query}!"

@app.function_name(name="DeleteIndex")
@app.route(route="index/{index_name}", methods=["DELETE"])
def main(req: func.HttpRequest) -> str:
    index_name = req.route_params.get("index_name")
    if not index_name:
        logging.error("Index name missing")
        return func.HttpResponse(body="Please provide input query", status_code=400)
    azure_search_service = AzureSearchService(index_name)
    azure_search_service.delete_index()
    return f"Index {index_name} deleted"

@app.function_name(name="CreateIndex")
@app.route(route="index", methods=["PUT"])
def main(req: func.HttpRequest) -> str:
    storage_account = os.environ['ADLS_STORAGE_ACCOUNT']
    storage_container = os.environ['ADLS_STORAGE_CONTAINER']
    document_path = os.environ['ADLS_KUSTO_DOCUMENT_PATH']
    
    try:
        req_body = req.get_json()
        file_name = req_body.get('fileName') if req_body else None
        index_name = req_body.get('indexName') if req_body else None
        if not file_name or not index_name:
            return func.HttpResponse("Missing file_name or index_name", status_code=400)
    except ValueError:
        return func.HttpResponse("Invalid input", status_code=400)
        
    datalake_tools = DataLakeTools(storage_account, storage_container, document_path)
    translation_examples = json.loads(datalake_tools.get_decoded_file_content(file_name))
    # logging.error(translation_examples)

    azure_search_service = AzureSearchService(index_name)
    result = azure_search_service.create_examples_search_index(translation_examples, llmchat=LLMChat())
    # Initialize the QueryAgent
    return func.HttpResponse(body=f"Index {index_name} created", status_code=201)

@app.function_name(name="QueryKQLQueryAgent")
@app.route(route="kqlquery", methods=["POST"])
def main(req: func.HttpRequest) -> str:
    storage_account = os.environ['ADLS_STORAGE_ACCOUNT']
    storage_container = os.environ['ADLS_STORAGE_CONTAINER']
    document_path = os.environ['ADLS_KUSTO_DOCUMENT_PATH']
    cluster = os.environ['ADLS_KUSTO_CLUSTER']
    database = os.environ['ADLS_KUSTO_DATABASE']
    
    input_query = req.params.get("query")

    try:
        req_body = req.get_json()
        input_query = req_body.get('query') if req_body else None
        db_schema_file_name = req_body.get('databaseSchemaFileName') if req_body else None
        language_reference_file_name = req_body.get('languageReferenceFileName') if req_body else None
        session_examples_file_name = req_body.get('sessionExampleFileName') if req_body else None
        if not input_query or not db_schema_file_name or not language_reference_file_name or not session_examples_file_name:
            return func.HttpResponse("Missing input parameters", status_code=400)
    except ValueError:
        return func.HttpResponse("Invalid input", status_code=400)
    
    kql_tools = KQLTools(cluster, database)
    datalake_tools = DataLakeTools(storage_account, storage_container, document_path)    
    azure_search_service = AzureSearchService(index_name="kqlsamples1")
    
    translation_examples = azure_search_service.search_examples_index(input_query, llmchat=LLMChat())
    database_schema = datalake_tools.get_decoded_file_content(db_schema_file_name)
    language_reference = datalake_tools.get_decoded_file_content(language_reference_file_name)
    session_examples = datalake_tools.get_decoded_file_content(session_examples_file_name)
    
    # Initialize the QueryAgent
    query_agent = QueryAgent(
        translation_examples=translation_examples,
        database_schema=database_schema,
        language_reference=language_reference,
        session_examples=session_examples,
        db_tools=kql_tools,
        language="Kusto Query Language",
        max_tries=3,
        debug=False
    )

    # Translate input query to KQL
    output_result = query_agent.query(input_query)

    return func.HttpResponse(body=json.dumps(output_result), status_code=200)
