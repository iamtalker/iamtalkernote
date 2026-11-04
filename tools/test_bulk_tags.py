"""여러 태그 삭제 정확성과 가져온 문서 대량 저장 회귀 시험."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

tmp = tempfile.TemporaryDirectory()
os.environ['APPDATA'] = tmp.name
Path(tmp.name, 'iamtalkernote').mkdir()
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import docs
from tagtext import edit_tags, note_tags


class BulkTagsTest(unittest.TestCase):
    def test_batch_delete_preserves_unselected_tags_and_protected_text(self):
        text = '---\ntags: [a, b, keep]\n---\n#a #b #keep https://example.com/#a\n`#a #b`\n\n태그: #a #b #keep\n'
        result, counts = edit_tags(text, ['a', 'b'], None)
        self.assertEqual(note_tags(result), {'keep'})
        self.assertIn('`#a #b`', result)
        self.assertIn('https://example.com/#a', result)
        self.assertEqual(counts['inline'], 2)

    def test_many_one_off_tags(self):
        tags = ['tag' + str(i) for i in range(2000)]
        text = '본문 ' + ' '.join('#' + t for t in tags) + '\n태그: #' + ' #'.join(tags)
        start = time.perf_counter()
        result, _ = edit_tags(text, tags, None)
        self.assertFalse(note_tags(result))
        self.assertIn('본문', result)
        print('2,000 tags in one note: %.3fs' % (time.perf_counter() - start))

    def test_imported_tags_batch_preserves_memo_and_refreshes_search(self):
        root = Path(tmp.name, 'imported'); root.mkdir(exist_ok=True)
        index = docs.DocIndex(); index.add_folder(str(root)); fid = index.fid(str(root))
        conn = index._db()
        rows, ann = [], []
        for i in range(2000):
            path = str(root / ('track%d.mp3' % i)); tag = 'oneoff%d' % i
            rows.append((path, fid, 'mp3', 1, 1, 1., 1., 'track%d' % i,
                         index.make_hay('track', path, '', [tag, 'keep'], 'memo'), None, 1, index.title_hay('track', 'mp3')))
            ann.append((path, json.dumps([tag, 'keep']), 'memo'))
        conn.executemany('INSERT INTO docs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', rows)
        conn.executemany('INSERT INTO annot VALUES (?,?,?)', ann); conn.commit(); conn.close()
        start = time.perf_counter()
        self.assertEqual(index.rename_tags(['oneoff%d' % i for i in range(2000)], None), 2000)
        self.assertTrue(all(tags == ['keep'] and memo == 'memo' for tags, memo in index.annots().values()))
        self.assertEqual(index.tag_use_count(['keep']), 2000)
        conn = index._db()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM docs WHERE instr(hay, 'oneoff') > 0").fetchone()[0], 0)
        conn.close()
        print('2,000 imported annotations: %.3fs' % (time.perf_counter() - start))


if __name__ == '__main__': unittest.main()
