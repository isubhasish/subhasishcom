import httpx

async def get_graph_link(content_json, title="Subhasish Encoder", author="Subhasish"):
    async with httpx.AsyncClient() as client:
        try:
            acc_resp = await client.get("https://api.telegra.ph/createAccount?short_name=SubhasishEncoder&author_name=Subhasish")
            token = acc_resp.json().get("result", {}).get("access_token")
            
            if not token:
                return "❌ Failed to generate Telegraph Token."
                
            payload = {
                "access_token": token,
                "title": title, 
                "author_name": author,
                "content": content_json, # FIX: Natively accepts pure JSON trees for perfect formatting!
                "return_content": True
            }
            r = await client.post("https://api.telegra.ph/createPage", json=payload)
            url = r.json().get("result", {}).get("url", "")
            
            if not url:
                return "❌ Telegraph API did not return a valid URL."
            
            return url.replace("telegra.ph", "graph.org")
        except Exception as e:
            return f"❌ Telegraph API Connection Error: {e}"