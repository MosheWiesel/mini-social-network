from tests.conftest import api, signup


def make_users(app):
    alice, bob, carol = app.test_client(), app.test_client(), app.test_client()
    signup(alice,"alice"); signup(bob,"bobuser"); signup(carol,"carol")
    return alice,bob,carol


def become_friends(alice, bob, bob_id):
    assert api(alice,"POST",f"/api/friend-requests/{bob_id}").status_code == 201
    alice_id=alice.get("/api/me").get_json()["data"]["user"]["id"]
    assert api(bob,"POST",f"/api/friend-requests/{alice_id}/accept").status_code == 200


def test_friend_request_duplicate_accept_cancel_reject_unfriend(app):
    alice,bob,carol=make_users(app)
    bob_id=bob.get("/api/me").get_json()["data"]["user"]["id"]
    carol_id=carol.get("/api/me").get_json()["data"]["user"]["id"]
    assert api(alice,"POST",f"/api/friend-requests/{bob_id}").status_code==201
    assert api(alice,"POST",f"/api/friend-requests/{bob_id}").status_code==409
    alice_id=alice.get("/api/me").get_json()["data"]["user"]["id"]
    assert api(bob,"POST",f"/api/friend-requests/{alice_id}/accept").status_code==200
    assert api(alice,"DELETE",f"/api/friends/{bob_id}").status_code==200
    assert api(alice,"POST",f"/api/friend-requests/{carol_id}").status_code==201
    assert api(alice,"POST",f"/api/friend-requests/{carol_id}/cancel").status_code==200
    assert api(carol,"POST",f"/api/friend-requests/{alice_id}").status_code==201
    assert api(alice,"POST",f"/api/friend-requests/{carol_id}/reject").status_code==200


def test_global_and_friends_feeds_visibility_and_blocks(app):
    alice,bob,carol=make_users(app);bob_id=bob.get("/api/me").get_json()["data"]["user"]["id"]
    become_friends(alice,bob,bob_id)
    public=api(alice,"POST","/api/posts",json={"content":"public hello","visibility":"public"}).get_json()["data"]
    private=api(alice,"POST","/api/posts",json={"content":"friends hello","visibility":"friends"}).get_json()["data"]
    global_bob=bob.get("/api/feed/global").get_json()["data"]
    friends_bob=bob.get("/api/feed/friends").get_json()["data"]
    global_carol=carol.get("/api/feed/global").get_json()["data"]
    assert [post["id"] for post in global_bob]==[public["id"]]
    assert {post["id"] for post in friends_bob}=={public["id"],private["id"]}
    assert [post["id"] for post in global_carol]==[public["id"]]
    alice_id=alice.get("/api/me").get_json()["data"]["user"]["id"]
    api(bob,"POST",f"/api/blocks/{alice_id}")
    assert bob.get("/api/feed/friends").get_json()["data"]==[]


def test_posts_poll_mentions_hashtags_reactions_comments_and_ownership(app):
    alice,bob,_=make_users(app)
    post=api(alice,"POST","/api/posts",json={"content":"Hello @bobuser #welcome","visibility":"public","poll":{"question":"Choose","options":["A","B"]}}).get_json()["data"]
    post_id=post["id"]
    assert post["mentions"][0]["username"]=="bobuser" and post["hashtags"]==["welcome"]
    assert api(bob,"POST",f"/api/posts/{post_id}/vote",json={"option":1}).status_code==200
    assert api(bob,"POST",f"/api/posts/{post_id}/vote",json={"option":0}).status_code==409
    assert api(bob,"POST",f"/api/posts/{post_id}/reaction").get_json()["data"]["count"]==1
    assert api(bob,"POST",f"/api/posts/{post_id}/reaction").get_json()["data"]["count"]==0
    comment=api(bob,"POST",f"/api/posts/{post_id}/comments",json={"content":"Nice"}).get_json()["data"]
    reply=api(alice,"POST",f"/api/posts/{post_id}/comments",json={"content":"Thanks","parentId":comment["id"]}).get_json()["data"]
    assert reply["parentId"]==comment["id"]
    assert api(alice,"PUT",f"/api/comments/{comment['id']}",json={"content":"hack"}).status_code==404
    assert api(bob,"DELETE",f"/api/posts/{post_id}").status_code==404
    assert api(alice,"PUT",f"/api/posts/{post_id}",json={"content":"edited #fresh","visibility":"public"}).status_code==200
    assert bob.get("/api/hashtags/fresh/posts").get_json()["data"][0]["id"]==post_id


def test_profile_edit_authorization_and_search(app):
    alice,bob,_=make_users(app)
    assert api(alice,"PUT","/api/me/profile",json={"username":"alice2","displayName":"Alice Doe","bio":"Hello","location":"IL","website":"https://example.com"}).status_code==200
    profile=bob.get("/api/users/alice2").get_json()["data"]
    assert profile["displayName"]=="Alice Doe" and "password" not in profile
    results=bob.get("/api/search?q=Alice").get_json()["data"]
    assert results["users"][0]["username"]=="alice2"
    assert bob.put("/api/me/profile",json={"username":"alice3"}).status_code==403


def test_bookmark_and_report(app):
    alice,bob,_=make_users(app)
    post=api(alice,"POST","/api/posts",json={"content":"save me","visibility":"public"}).get_json()["data"]
    assert api(bob,"POST",f"/api/posts/{post['id']}/bookmark").get_json()["data"]["bookmarked"]
    assert bob.get("/api/bookmarks").get_json()["data"][0]["id"]==post["id"]
    assert api(bob,"POST","/api/reports",json={"targetType":"post","targetId":post["id"],"reason":"spam","details":"test"}).status_code==201


def test_notifications_for_comment_mention_and_reaction(app):
    alice,bob,_=make_users(app)
    post=api(alice,"POST","/api/posts",json={"content":"hello","visibility":"public"}).get_json()["data"]
    api(bob,"POST",f"/api/posts/{post['id']}/reaction")
    api(bob,"POST",f"/api/posts/{post['id']}/comments",json={"content":"Hi @alice"})
    notifications=alice.get("/api/notifications").get_json()
    kinds={item["kind"] for item in notifications["data"]}
    assert {"reaction","comment","mention"} <= kinds
    assert notifications["meta"]["unread"] >= 3
    assert api(alice,"POST","/api/notifications/read-all").status_code==200
    assert alice.get("/api/notifications").get_json()["meta"]["unread"]==0
