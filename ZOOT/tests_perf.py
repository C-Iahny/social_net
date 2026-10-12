"""Garde-fous de performance : le nombre de requêtes des points chauds ne
doit plus croître avec le volume (stories, historique de chat, liste d'amis,
commentaires du fil)."""
from asgiref.sync import async_to_sync
from django.test import TestCase, Client
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse

from account.models import Account
from stories.models import Story, StoryView


class QueryBudgetTests(TestCase):
    def setUp(self):
        self.me = Account.objects.create_user(email='perf@test.mg', username='perf', password='pw12345678')
        self.others = [Account.objects.create_user(email=f'o{i}@test.mg', username=f'o{i}', password='pw12345678') for i in range(3)]
        self.c = Client()
        self.c.force_login(self.me)

    def _count(self, url):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.c.get(url)
        self.assertEqual(resp.status_code, 200, url)
        return len(ctx.captured_queries)

    def test_story_feed_queries_do_not_grow_with_stories(self):
        for i in range(2):
            Story.objects.create(user=self.others[i % 3], story_type='text', caption=f's{i}')
        small = self._count(reverse('stories:feed'))
        for i in range(18):
            s = Story.objects.create(user=self.others[i % 3], story_type='text', caption=f'b{i}')
            if i % 2:
                StoryView.objects.create(story=s, viewer=self.me)
        big = self._count(reverse('stories:feed'))
        self.assertEqual(small, big)
        self.assertLessEqual(big, 6)
        data = self.c.get(reverse('stories:feed')).json()
        groups = data['groups'] if isinstance(data, dict) and 'groups' in data else data
        total = sum(len(g['stories']) for g in groups)
        self.assertEqual(total, 20)
        seen = sum(1 for g in groups for s in g['stories'] if s['seen'])
        self.assertEqual(seen, 9)

    def test_chat_history_queries_do_not_grow_with_messages(self):
        from chat.models import PrivateChatRoom, RoomChatMessage, MessageReaction
        from chat.consumers import get_room_chat_messages
        room = PrivateChatRoom.objects.create(user1=self.me, user2=self.others[0])
        first = RoomChatMessage.objects.create(user=self.me, room=room, content='bonjour')
        for i in range(25):
            m = RoomChatMessage.objects.create(user=self.others[0], room=room, content=f'm{i}', reply_to=first if i % 3 == 0 else None)
            if i % 4 == 0:
                MessageReaction.objects.create(message=m, user=self.me, emoji='👍')
        with CaptureQueriesContext(connection) as ctx:
            payload = async_to_sync(get_room_chat_messages)(room, 1)
        self.assertIsNotNone(payload)
        self.assertLessEqual(len(ctx.captured_queries), 8, [q['sql'][:80] for q in ctx.captured_queries])

    def test_friend_list_queries_do_not_grow_with_friends(self):
        from friend.models import FriendList
        mine, _ = FriendList.objects.get_or_create(user=self.me)
        for o in self.others:
            mine.friends.add(o)
            fl, _ = FriendList.objects.get_or_create(user=o)
            fl.friends.add(self.me)
        n3 = self._count(reverse('friend:list', kwargs={'user_id': self.me.pk}))
        more = [Account.objects.create_user(email=f'm{i}@test.mg', username=f'm{i}', password='pw12345678') for i in range(10)]
        for o in more:
            mine.friends.add(o)
        n13 = self._count(reverse('friend:list', kwargs={'user_id': self.me.pk}))
        self.assertEqual(n3, n13)

    def test_feed_comments_are_bounded(self):
        from post.models import Post, Comment
        from post.comments_utils import load_comments_grouped
        p = Post.objects.create(author=self.me, title='t', body='b')
        for i in range(60):
            Comment.objects.create(post=p, author=self.me, body=f'c{i}')
        top, totals = load_comments_grouped([p.id], cap=20)
        self.assertEqual(totals[p.id], 60)
        self.assertEqual(len(top[p.id]), 20)
        self.assertEqual(top[p.id][-1].body, 'c59')      # les plus récents, ordre chronologique
