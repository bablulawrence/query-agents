import azure.functions as func

app = func.FunctionApp()

@app.function_name(name="QueryAgent")
@app.route(route="req")
def main(req: func.HttpRequest) -> str:
    query = req.params.get("query")
    return f"This is your query, {query}!"