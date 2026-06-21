"""Live data endpoint for the Cologic site (Modal, read-only, CORS-open).

Serves the single site record (benchmark + foundry state) the frontend fetches.
The eval pipeline writes the record into the Modal Dict via cologic.store.publish;
this app just reads and serves it.

  modal deploy serve.py
  curl https://<your-deploy>--cologic-web-web.modal.run/state

GET /state   -> the latest record (or {"source":"empty"} before the first seed)
GET /health  -> {"ok": true}
"""

import modal

app = modal.App("cologic-web")
state = modal.Dict.from_name("cologic-state", create_if_missing=True)
image = modal.Image.debian_slim().pip_install("fastapi[standard]")


@app.function(image=image, min_containers=1)
@modal.asgi_app()
def web():
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    api = FastAPI(title="cologic-web")
    api.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"]
    )

    @api.get("/health")
    def health():
        return {"ok": True}

    @api.get("/state")
    def get_state():
        return state.get("latest", {"source": "empty"})

    return api
