import os
from fastapi import APIRouter, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from routes.auth import auth_required
from datetime import datetime
from enum import Enum
from globals import get_conn, sessions
from utils import Exception400
import box_api
from loguru import logger

storage_router = APIRouter(prefix='/storage', tags=['Access to storage'])

class User(BaseModel):
    id: int
    name: str
    contact: str | None = None
    stories: list[int] | None = Field(default=None, description='May be null. Be careful')
    reviews: list[int] | None = Field(default=None, description='May be null. Be careful')

class Story(BaseModel):
    id: int
    author: int
    name: str
    votes: int
    reviews: list[int] | None = Field(default=None, description='May be null. Be careful')
    private: bool
    created_at: datetime
    updated_at: datetime

class Review(BaseModel):
    id: int
    author: int
    story: int
    content: str
    votes: int
    created_at: datetime

class ParamEnum(str, Enum):
    votes = 'votes'
class TypeEnum(str, Enum):
    stories = 'stories'
    reviews = 'reviews'

class IncreaseParamRequest(BaseModel):
    sid: str
    id: int = Field(description="Story or review id")
    param: ParamEnum
    type: TypeEnum
    up_or_down: int | None = Field(default=1, description="Required only for votes.", ge=-1, le=1)

class IncreaseParamResponse(BaseModel):
    new_value: int

class GetByIdRequest(BaseModel):
    id: int
    sid: str | None = Field(description="Session id returned by login or reg route",
                            default=None)
    detailed: bool = False


class StoriesListingTypeEnum(str, Enum):
    home = 'home'
    best = 'best'
    user = 'user'

class ListStoriesRequest(BaseModel):
    listing_type: StoriesListingTypeEnum = Field(default=StoriesListingTypeEnum.home, description='Do not pass this argument please, because work in progress. And probably, it will be forver WIP :/')
    sid: str | None = Field(default=None, description='Required only to view private stories (e.g. "My projects" page)')
    offset: int = 0
    limit: int = 15

class ListStoriesResponse(BaseModel):
    stories: list[Story]

class ListStoryAssetsRequests(BaseModel):
    story_id: int

class ListStoryAssetsResponse(BaseModel):
    assets: list[str] = Field(description='List of names of assets. Can be empty')

class DeleteAssetRequest(BaseModel):
    sid: str
    story_id: int = Field(description="Story id")
    name: str = Field(description="Asset name")

class UpdateStoryContentRequest(BaseModel):
    sid: str
    id: int
    content: str

class UpdateStoryProperties(BaseModel):
    sid: str
    id: int
    private: bool | None = Field(default=None, description='Use only if this property was changed by user')
    name: str | None = Field(default=None, description='Use ONLY if this property was changed by user')

class ContentResponse(BaseModel):
    content: str
    result: str = Field(default='OK')

class NewStoryRequest(BaseModel):
    sid: str
    name: str
    content: str

class DeleteStoryRequest(BaseModel):
    sid: str
    id: int = Field(description="Story id")

class NewreviewRequest(BaseModel):
    sid: str
    story: int
    content: str

class DeletereviewRequest(BaseModel):
    sid: str
    id: int = Field(description="Review id")


@storage_router.put('/user_by_id')
async def user_by_id(r: GetByIdRequest) -> User:
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT name FROM sf.users WHERE id=\'{r.id}\'")
            row = cur.fetchone()
            name = row[0]
            stories, reviews = None, None
            if r.detailed:
                cur.execute("SELECT id, author FROM sf.stories "
                            f"WHERE author=\'{r.id}\'")
                stories = [i[0] for i in cur.fetchall()]
                cur.execute("SELECT id, author FROM sf.reviews "
                            f"WHERE author=\'{r.id}\'")
                reviews = [i[0] for i in cur.fetchall()]
            return User(id=r.id, name=name, stories=stories, reviews=reviews)


@storage_router.get('/random_story')
async def random_story() -> Story:
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM sf.stories WHERE not private ORDER BY random() LIMIT 1")
            row = cur.fetchone()
            cols = {k.name: v for k, v in zip(cur.description, row)}
            cur.execute(f"SELECT id, author FROM sf.reviews WHERE story=\'{cols['id']}\'")
            reviews = [i[0] for i in cur.fetchall()]
            return Story(**cols, reviews=reviews)

@storage_router.put('/story_by_id')
async def story_by_id(r: GetByIdRequest) -> Story:
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM sf.stories WHERE id=\'{r.id}\'")
            row = cur.fetchone()
            cols = {k.name: v for k, v in zip(cur.description, row)}
            if cols['private'] and (r.sid is None or r.sid not in sessions or\
                                    sessions[r.sid]['uid'] != cols['author']):
                raise Exception400('Invalid session id')
            reviews = None
            if r.detailed:
                cur.execute(f"SELECT id, author FROM sf.reviews WHERE story=\'{r.id}\'")
                reviews = [i[0] for i in cur.fetchall()]
            return Story(**cols, reviews=reviews)

@storage_router.put('/review_by_id')
async def review_by_id(r: GetByIdRequest) -> Review:
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM sf.reviews WHERE id=\'{r.id}\'")
            row = cur.fetchone()
            return Review(**{k.name: v for k, v in zip(cur.description, row)})

@storage_router.post('/new_story')
@auth_required
async def new_story(r: NewStoryRequest) -> Story:
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO sf.stories (name, author) VALUES'
                        f"('{r.name}',{sessions[r.sid]['uid']}) RETURNING *")
            row = cur.fetchone()
            conn.commit()
            box_api.upload(r.content.encode('utf-8'), f'{os.environ['STORAGE_PREFIX']}/stories/{row[0]}.xml')
            return Story(**{k.name: v for k, v in zip(cur.description, row)}, reviews=[])

@storage_router.post('/new_review')
@auth_required
async def new_review(r: NewreviewRequest) -> Review:
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO sf.reviews (author, story, content) VALUES'
                        f"({sessions[r.sid]['uid']}, {r.story}, '{r.content}') RETURNING *")
            row = cur.fetchone()
            conn.commit()
        return Review(**{k.name: v for k, v in zip(cur.description, row)})

@storage_router.put('/story_content')
async def story_content(r: GetByIdRequest):
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT private, author, id FROM sf.stories WHERE id='{r.id}'")
            row = cur.fetchone()
            if row[0] and (r.sid is None or r.sid not in sessions or
                           sessions[r.sid]['uid'] != row[1]):
                raise Exception400('Invalid session id')
            return ContentResponse(content=box_api.file_content(f'{os.environ['STORAGE_PREFIX']}/stories/{r.id}.xml'))

_order_by = {
    'best': 'votes, created_at, id',
    'home': 'power((votes+1)*cast(extract(epoch from updated_at) as BigInt), 2), id',
    'user': 'updated_at, id'
}
@storage_router.put('/list_stories')
async def list_stories(r: ListStoriesRequest) -> ListStoriesResponse:
    """ATTENTION! This endpoint puts null/None into the reviews field.
    If you want get a specific user's stories, provide his SID."""
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            if r.listing_type.name == 'user' and (r.sid is None or r.sid not in sessions):
                raise Exception400('Invalid session id')
            cur.execute(f"SELECT * FROM sf.stories {f'WHERE author={sessions[r.sid]['uid']}'
                                                    if r.listing_type.name == 'user' else ''}\n"
                        f"ORDER BY {_order_by[r.listing_type.name]} DESC LIMIT {r.limit} OFFSET {r.offset}")
            stories=[Story(**{ k.name: v for k, v in zip(cur.description, row)}) for row in cur.fetchall()]
            return ListStoriesResponse(stories=stories)

@storage_router.post('/update_story_content')
async def update_story_content(r: UpdateStoryContentRequest):
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT private, author, id FROM sf.stories WHERE id='{r.id}'")
            row = cur.fetchone()
            if r.sid is None or r.sid not in sessions or sessions[r.sid]['uid'] != row[1]:
                raise Exception400('Invalid session id')
    box_api.upload(r.content.encode(), f'{os.environ['STORAGE_PREFIX']}/stories/{r.id}.xml')
    return {"result": "OK"}

@storage_router.post('/update_story_properties')
async def update_story_properties(r: UpdateStoryProperties):
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT author, id FROM sf.stories WHERE id=\'{r.id}\'")
            row = cur.fetchone()
            if r.sid is None or r.sid not in sessions or row[0] != sessions[r.sid]['uid']:
                raise Exception400('Invalid session id')
            if r.private is not None:
                cur.execute(f"UPDATE sf.stories\n"
                            f"SET private={r.private}\n"
                            f"WHERE id={r.id}")
            if r.name is not None:
                cur.execute(f"UPDATE sf.stories\n"
                            f"SET name='{r.name}'\n"
                            f"WHERE id={r.id}")
            conn.commit()
    return {'result': 'OK'}

@storage_router.get('/asset_content/{story_id}/{name}')
async def asset_content(story_id: int, name: str):
    return Response(box_api.file_content(f'{os.environ['STORAGE_PREFIX']}/assets/{story_id}/{name}', decode=False))#, media_type="image/png")

@storage_router.post('/new_asset')
async def new_asset(file: UploadFile, sid: str, story_id: int):
    story = await story_by_id(GetByIdRequest(id=story_id))
    if sid not in sessions or story.author != sessions[sid]['uid']:
        raise Exception400('Invalid session id')
    box_api.upload(await file.read(), f'{os.environ['STORAGE_PREFIX']}/assets/{story_id}/{file.filename}')
    logger.info(f'Uploaded to {os.environ['STORAGE_PREFIX']}/assets/{story_id}/{file.filename}')
    return {'result': 'OK'}

@storage_router.delete('/delete_asset')
async def delete_asset(r: DeleteAssetRequest):
    story = await story_by_id(GetByIdRequest(id=r.story_id))
    if r.sid not in sessions or story.author != sessions[r.sid]['uid']:
        raise Exception400('Invalid session id')
    logger.info(f'Deleting {os.environ['STORAGE_PREFIX']}/assets/{r.story_id}/{r.name}')
    box_api.delete(f'{os.environ['STORAGE_PREFIX']}/assets/{r.story_id}/{r.name}')
    return {'result': 'OK'}

@storage_router.get('/list_story_assets/{story_id}')
async def list_story_assets(story_id: int) -> ListStoryAssetsResponse:
    return ListStoryAssetsResponse(assets=
                                   [i.name for i in
                                    box_api.list_files(f'{os.environ['STORAGE_PREFIX']}/assets/{story_id}/')])

@storage_router.post('/increase_param')
async def increase_param(r: IncreaseParamRequest) -> IncreaseParamResponse:
    story = await story_by_id(GetByIdRequest(id=r.id))
    if r.sid not in sessions or story.author != sessions[r.sid]['uid']:
        raise Exception400('Invalid session id')
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE sf.{r.type.name}\n"
                        f"SET {r.param.name}={r.param.name}+1*{r.up_or_down}\n"
                        f"WHERE id={r.id}\n"
                        f"RETURNING {r.param.name}")
            row = cur.fetchone()
            conn.commit()
            return IncreaseParamResponse(new_value=row[0])