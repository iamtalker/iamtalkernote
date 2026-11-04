"""자동 태그: 한글 우선·메타데이터 제외·혼합 문서·기존 태그 보존·재실행·변경 감지."""
import os
import sys
import tempfile
import unittest

tmp = tempfile.TemporaryDirectory()
os.environ['APPDATA'] = tmp.name
os.makedirs(os.path.join(tmp.name, 'iamtalkernote'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
import autotags
import docs
import store
import tagac


class AutoTagsTest(unittest.TestCase):
    def test_korean_first_and_metadata(self):
        text = '---\nip: link link link\nmemo: 메모 메모 메모\n---\n'
        text += '[정부](https://example.com/link) 북한은 북한의 병원은 병원을 의료장비는 의료장비를 '
        text += 'ip link memo ' * 20 + '&#x20;'
        result = tagac.content_suggestions(text)
        self.assertEqual(set(result), {'북한', '병원', '의료장비'})
        self.assertEqual(autotags.additions(text, ['북한']), [t for t in result if t != '북한'])

    def test_known_tags_are_prioritized_only_when_present(self):
        text = '병원은 병원을 병원에서 북한은 북한의 의료장비는 의료장비를 Python'
        self.assertEqual(tagac.content_suggestions(text, known=['Python', '북한', '없는태그']),
                         ['북한', 'Python', '병원'])
        self.assertEqual(tagac.content_suggestions(text, have=['북한'], known=['북한']),
                         ['병원', '의료장비', 'python'])

    def test_all_three_slots_can_use_known_tags_in_either_language(self):
        text = 'Python ' * 5 + '병원은 병원을 북한의 ' + '새단어 ' * 20
        self.assertEqual(tagac.content_suggestions(text, known=['Python', '병원', '북한']),
                         ['Python', '병원', '북한'])

    def test_particles(self):
        self.assertEqual(tagac.content_suggestions('사과는 사과를 사과은 바나나는 바나나를 포도를 포도는 은 는 을 를'),
                         ['사과', '바나나', '포도'])

    def test_mixed_documents_and_repeat(self):
        root = os.path.join(tmp.name, 'notes'); os.makedirs(root, exist_ok=True)
        external = os.path.join(tmp.name, 'external'); os.makedirs(external, exist_ok=True)
        path = os.path.join(root, 'note.md')
        body = '사과는 사과를 바나나는 바나나를 포도는 포도를\n\n태그: #기존\n'
        with open(path, 'w', encoding='utf-8') as f: f.write(body)
        imported = os.path.join(external, 'doc.txt')
        with open(imported, 'w', encoding='utf-8') as f: f.write(body)
        note_store = store.Store(root)
        doc_index = docs.DocIndex(); doc_index.add_folder(external); doc_index.scan()
        doc_index.set_annot(imported, tags=['원래'], memo='메모 보존')
        targets = note_store.list_notes('*') + doc_index.list_docs()
        progress = lambda *args: None
        rows, errors = autotags.plan(targets, progress, lambda: False)
        self.assertFalse(errors); self.assertEqual(len(rows), 2)
        # 미리보기 후 추가된 태그도 유지한다.
        doc_index.set_annot(imported, add_tags=['추가됨'])
        self.assertEqual(autotags.apply(rows, note_store, doc_index, progress, lambda: False), (2, 0, []))
        tags, memo = doc_index.annots()[imported]
        self.assertTrue({'원래', '추가됨', '사과', '바나나', '포도'} <= set(tags))
        self.assertEqual(memo, '메모 보존')
        with open(imported, encoding='utf-8') as f: self.assertEqual(f.read(), body)
        rows, errors = autotags.plan(note_store.list_notes('*') + doc_index.list_docs(), progress, lambda: False)
        self.assertEqual(rows, []); self.assertFalse(errors)

    def test_changed_content_is_skipped(self):
        class Note(dict):
            def read(self): return '분석 뒤 바뀐 본문'
        n = Note(path='changed.md')
        self.assertEqual(autotags.apply([(n, autotags.digest('원래 본문'), ['원래'])], None, None,
                                       lambda *args: None, lambda: False), (0, 1, []))


if __name__ == '__main__':
    unittest.main()
