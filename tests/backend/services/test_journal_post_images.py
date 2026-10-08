"""Persist and serialize real PostImage rows; never touch production data."""
import pytest
from sqlalchemy import event
from web.backend.database.models import CommunityCategory, Post, PostImage
from web.backend.services.community import CommunityService


@pytest.fixture
def category(db_session):
    item=CommunityCategory(name='合成记录分类');db_session.add(item);db_session.commit();return item


@pytest.mark.parametrize('metas',[
    [{'image_url':'original.png','body_site':'left_hand','capture_date':'2026-09-14'}],
    [{'image_url':'original.png','body_site':'left_hand'},{'image_url':'art.png'},{'image_url':'overlay.png'}],
    None,
])
def test_all_images_survive_partial_metadata_in_requested_order(db_session,test_user,category,metas):
    expected=['art.png','overlay.png','original.png'];service=CommunityService(db_session)
    post=service.create_post(test_user.id,'合成创意','<p>创意短句</p><p>占比12.4%；3处</p>',category.id,image_urls=expected,image_metas=metas,post_type='image')
    db_session.expire_all()
    rows=db_session.query(PostImage).filter_by(post_id=post.id).order_by(PostImage.order).all()
    assert [r.image_url for r in rows]==expected and [r.order for r in rows]==[0,1,2]
    serialized=service.post_to_model(db_session.get(Post,post.id),test_user.id)
    assert [image.image_url for image in serialized.images]==expected
    assert '12.4%' in serialized.content and '3处' in serialized.content
    if metas:assert rows[-1].body_site=='left_hand'


def test_metadata_only_legacy_client_still_works(db_session,test_user,category):
    post=CommunityService(db_session).create_post(test_user.id,'合成','合成内容',category.id,image_metas=[{'image_url':'only.png'}])
    assert db_session.query(PostImage).filter_by(post_id=post.id).one().image_url=='only.png'


def test_image_failure_does_not_leave_an_empty_published_post(db_session,test_user,category):
    def reject(mapper,connection,target):raise RuntimeError('synthetic insert failure')
    event.listen(PostImage,'before_insert',reject)
    try:
        with pytest.raises(RuntimeError):CommunityService(db_session).create_post(test_user.id,'atomic-test','合成内容',category.id,image_urls=['image.png'])
        db_session.rollback()
        assert db_session.query(Post).filter_by(title='atomic-test').count()==0
    finally:event.remove(PostImage,'before_insert',reject)
