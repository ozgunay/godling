"""The site's rules and blocked words, read from the database: changed in the admin, they hold at once."""
import re
from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.credits import services as credits
from apps.notes import services as notes
from apps.notes.models import Note
from apps.rules import words
from apps.rules.models import BlockedWord, Rules
from apps.users.models import User

PASSWORD = "an-island-test-pass-4127"


class RulesTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_there_is_one_rules_row_with_the_old_defaults(self):
        rules = Rules.get()
        self.assertEqual((rules.welcome_credits, rules.free_powers, rules.power_every, rules.note_every,
                          rules.note_limit, rules.reports_to_hide), (20, False, 2, 180, 140, 3))
        Rules(welcome_credits=5).save()  # a second save is the same row
        self.assertEqual(Rules.objects.count(), 1)
        self.assertEqual(Rules.get().welcome_credits, 5)

    def test_welcome_credits_follow_the_rules(self):
        Rules.objects.filter(pk=1).update(welcome_credits=7)
        self.client.post(reverse("account_signup"), {"username": "mara_k", "email": "mara@example.org",
                                                     "password1": PASSWORD, "password2": PASSWORD})
        self.client.post(re.search(r"https?://\S+/accounts/confirm-email/\S+/", mail.outbox[-1].body).group(0))
        self.assertEqual(credits.balance_of(User.objects.get(username="mara_k")), 7)

    def test_reports_to_hide_follow_the_rules(self):
        Rules.objects.filter(pk=1).update(reports_to_hide=1)
        author = User.objects.create_user(username="mara_k", email="m@example.org", password=PASSWORD)
        reporter = User.objects.create_user(username="tomv", email="t@example.org", password=PASSWORD)
        User.objects.filter(pk=reporter.pk).update(date_joined=timezone.now() - timedelta(days=2))  # old enough to count
        note = Note.objects.create(author=author, text="hello")
        notes.report(note, reporter, "spam")
        note.refresh_from_db()
        self.assertEqual(note.status, Note.HIDDEN)


class BlockedWordTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_the_seeded_words_hold(self):
        self.assertTrue(words.note_blocked("you are a Retard"))
        self.assertFalse(words.note_blocked("lovely grapes on the beach"))  # "rape" matches a word's start only
        self.assertTrue(words.username_blocked("xXHitlerXx"))
        self.assertFalse(words.username_blocked("grapefan"))

    def test_staff_add_and_switch_off_words(self):
        word = BlockedWord.objects.create(word="Cheap Gold", applies_to=BlockedWord.BOTH)
        self.assertEqual(word.word, "cheap gold")
        self.assertTrue(words.note_blocked("get cheap gold here"))
        self.assertTrue(words.username_blocked("cheapgold99"))
        word.active = False
        word.save()
        self.assertFalse(words.note_blocked("get cheap gold here"))

    def test_a_username_with_a_blocked_word_is_refused_at_signup(self):
        BlockedWord.objects.create(word="spamking", applies_to=BlockedWord.USERNAMES)
        self.client.post(reverse("account_signup"), {"username": "TheSpamKing", "email": "s@example.org",
                                                     "password1": PASSWORD, "password2": PASSWORD})
        self.assertFalse(User.objects.filter(username="TheSpamKing").exists())

    def test_an_empty_table_still_blocks_the_seed(self):
        BlockedWord.objects.all().delete()
        words.forget()
        self.assertTrue(words.note_blocked("fuck"))
