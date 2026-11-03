"""Moderating notes in the admin: hide, restore, mute, unmute and ban from the notes' list, and the reports' list."""
from django.test import TestCase

from apps.notes.models import Note, Report
from apps.users.models import User


class NoteAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(username="keeper", email="keeper@example.org",
                                                   password="an-island-test-pass-4127")
        self.client.force_login(self.staff)
        self.author = User.objects.create_user(username="tomv", email="tomv@example.org", password="x-test-pass-0001")
        self.reader = User.objects.create_user(username="mara", email="mara@example.org", password="x-test-pass-0002")
        self.note = Note.objects.create(author=self.author, text="hello island")
        self.report = Report.objects.create(note=self.note, reporter=self.reader, reason=Report.SPAM)

    def act(self, action, model="note", pk=None):
        return self.client.post(f"/admin/notes/{model}/", {"action": action, "_selected_action": [pk or self.note.pk]},
                                follow=True)

    def test_the_words_for_notes_and_reports(self):
        self.assertEqual(str(self.note), "tomv: hello island")
        self.assertEqual(str(self.report), f"mara on #{self.note.pk}: spam")

    def test_hide_and_restore(self):
        self.assertContains(self.act("hide"), "1 note(s) hidden.")
        self.note.refresh_from_db()
        self.report.refresh_from_db()
        self.assertEqual(self.note.status, Note.HIDDEN)
        self.assertTrue(self.report.reviewed)
        self.assertContains(self.act("restore"), "1 note(s) restored.")
        self.note.refresh_from_db()
        self.assertEqual(self.note.status, Note.SENT)

    def test_mute_unmute_and_ban_the_author(self):
        self.assertContains(self.act("mute_authors"), "1 account(s) muted.")
        self.author.refresh_from_db()
        self.assertTrue(self.author.notes_muted)
        self.assertContains(self.act("unmute_authors"), "1 account(s) unmuted.")
        self.author.refresh_from_db()
        self.assertFalse(self.author.notes_muted)
        self.assertContains(self.act("ban_authors"), "1 account(s) banned")
        self.author.refresh_from_db()
        self.assertFalse(self.author.is_active)
        staff_note = Note.objects.create(author=self.staff, text="from the keeper")
        self.assertContains(self.act("ban_authors", pk=staff_note.pk), "0 account(s) banned")

    def test_the_reports_list_shows_the_note_and_its_author(self):
        page = self.client.get("/admin/notes/report/")
        self.assertContains(page, "hello island")
        self.assertContains(page, "tomv")
        self.assertEqual(self.client.get("/admin/notes/report/add/").status_code, 403)
        self.assertEqual(self.client.get("/admin/notes/note/add/").status_code, 403)
