import httpx

async def get_graph_link(text):
    async with httpx.AsyncClient() as client:
        payload = {
            "title": "MediaInfo Details", "author_name": "Gemini Compressor",
            "content": [{"tag": "pre", "children": [text]}], "return_content": True
        }
        try:
            r = await client.post("https://api.telegra.ph/createPage", json=payload)
            return r.json().get("result", {}).get("url", "Failed to generate link")
        except:
            return "Failed to connect to Telegraph API."