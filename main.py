from loguru import logger
import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.requests import Request
from fastapi.middleware.cors import CORSMiddleware

import box_api
from routes import auth, storage
from utils import Exception400

try:
    box_api.login('')
    logger.info('Dropbox has been authorized')
except:
    logger.info('Please open "/dbx" page')

app = FastAPI(
    title="StoryForge",
    summary="Use this API to access stories and manage sessions.",
    version="0.1.0",
    contact={
        'name': 'GitHub repository',
        'url': 'https://github.com/Moohomor/sf-fastapi'
    }
)
app.include_router(auth.auth_router)
app.include_router(storage.storage_router)
# app.include_router(ai_routes.ai_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def handle_500(_: Request, ex: Exception):
    return JSONResponse({'result': str(ex)
                        if os.environ.get('SHOW_EXCEPTIONS', '0') == '1' else 'ERROR'},
                        400 if isinstance(ex, Exception400) else 500)


@app.get('/ping')
async def ping():
    return 'pong'

@app.get('/dbx')
def dropbox_auth_page() -> HTMLResponse:
    """Get Dropbox authorization instructions"""
    if box_api.authorized():
        return "Dropbox is already authorized"
    return HTMLResponse(content=(f'1. Go to this <a target="DBX Auth" href="{box_api.get_link()}">page</a><br>'
                                 f"2. Click \"Allow\" (you might have to log in first).<br>"
                                 f"3. Copy the authorization code.<br>"
                                 f"4. Insert it in URL after /dbx/"))

@app.get('/dbx/{token}')
def get_dropbox_token_page(token: str):
    """Authorize Dropbox with token"""
    try:
        box_api.login(token.strip())
        return "Dropbox initialized successfully"
    except Exception as e:
        logger.exception('Exception in get_token_page')
        return str(e) if os.environ.get('SHOW_EXCEPTIONS', '0') == '1' else 'ERROR', 500


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8000')))