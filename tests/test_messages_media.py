import io

from PIL import Image

from tests.conftest import api, signup
from tests.test_social_content import become_friends


def test_private_messages_membership_unread_and_block(app):
    alice,bob,carol=app.test_client(),app.test_client(),app.test_client();signup(alice,"alice");signup(bob,"bobuser");signup(carol,"carol")
    bob_id=bob.get("/api/me").get_json()["data"]["user"]["id"]
    conversation=api(alice,"POST","/api/conversations",json={"userId":bob_id}).get_json()["data"]
    cid=conversation["id"]
    assert api(alice,"POST",f"/api/conversations/{cid}/messages",json={"content":"secret"}).status_code==201
    assert carol.get(f"/api/conversations/{cid}/messages").status_code==404
    assert bob.get("/api/conversations").get_json()["data"][0]["unread"]==1
    assert bob.get(f"/api/conversations/{cid}/messages").get_json()["data"][0]["content"]=="secret"
    alice_id=alice.get("/api/me").get_json()["data"]["user"]["id"]
    api(bob,"POST",f"/api/blocks/{alice_id}")
    assert api(alice,"POST",f"/api/conversations/{cid}/messages",json={"content":"blocked"}).status_code==403


def test_upload_validation_and_private_attachment_authorization(app):
    alice,bob,carol=app.test_client(),app.test_client(),app.test_client();signup(alice,"alice");signup(bob,"bobuser");signup(carol,"carol")
    bad=api(alice,"POST","/api/media",data={"kind":"post","file":(io.BytesIO(b"<svg></svg>"),"x.svg")},content_type="multipart/form-data")
    assert bad.status_code==422
    image=Image.new("RGB",(12,12),(90,80,200));buffer=io.BytesIO();image.save(buffer,"PNG");buffer.seek(0)
    uploaded=api(alice,"POST","/api/media",data={"kind":"post","file":(buffer,"../../avatar.png")},content_type="multipart/form-data")
    assert uploaded.status_code==201
    media_id=uploaded.get_json()["data"]["id"]
    assert alice.get(f"/api/media/{media_id}").status_code==200
    post=api(alice,"POST","/api/posts",json={"content":"image post","visibility":"public","media":[media_id]})
    assert post.status_code==201 and post.get_json()["data"]["media"][0]["id"]==media_id
    video=api(alice,"POST","/api/media",data={"kind":"post","file":(io.BytesIO(b"\x00\x00\x00\x18ftypisom0000"),"clip.mp4")},content_type="multipart/form-data")
    assert video.status_code==201 and video.get_json()["data"]["mimeType"]=="video/mp4"
    bob_id=bob.get("/api/me").get_json()["data"]["user"]["id"]
    cid=api(alice,"POST","/api/conversations",json={"userId":bob_id}).get_json()["data"]["id"]
    buffer=io.BytesIO();image.save(buffer,"PNG");buffer.seek(0)
    private=api(alice,"POST","/api/media",data={"kind":"message","conversationId":str(cid),"file":(buffer,"private.png")},content_type="multipart/form-data").get_json()["data"]
    assert bob.get(f"/api/media/{private['id']}").status_code==200
    assert carol.get(f"/api/media/{private['id']}").status_code==404
