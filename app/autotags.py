"""문서별 빈도 상위 세 단어. 기존 태그를 유지하고 재실행해도 늘어나지 않는다."""
import hashlib
import os

import docs
import store
import tagac
from tagtext import add_tag, note_tags, TAG_LINE


def digest(body):
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def suggestion_text(body, title):
    fm = store.FM_RE.match(body)
    text = body[fm.end():] if fm else body
    if TAG_LINE.sub("", text).strip():
        return text
    stem = os.path.splitext(title)[0]
    return stem.replace('_', ' ').replace('-', ' ')


def additions(body, have=(), known=()):
    fm = store.FM_RE.match(body)
    text = body[fm.end():] if fm else body
    existing = {str(t).casefold() for t in have}
    return [t for t in tagac.content_suggestions(text, known=known) if t.casefold() not in existing]


def recommendations(body, title, have=(), known=(), extension='', existing_only=False):
    tags = additions(suggestion_text(body, title), have, known)
    if existing_only:
        vocabulary = {str(t).casefold() for t in known}
        tags = [t for t in tags if t.casefold() in vocabulary]
    ext = str(extension).lower().lstrip('.')
    existing = {str(t).casefold() for t in have} | {t.casefold() for t in tags}
    if ext and ext not in {'txt', 'md'} and tagac.clean(ext) and ext not in existing:
        tags.append(ext)
    return tags


def plan(targets, progress, cancelled, known=(), existing_only=False):
    rows, errors = [], []
    for i, n in enumerate(targets):
        if cancelled():
            break
        try:
            body = n.read()
            imported = isinstance(n, docs.Doc)
            have = n.get('tags', ()) if imported else note_tags(body)
            tags = recommendations(body, n['title'], have, known, n.get('ext', 'md') if imported else 'md', existing_only)
            if tags:
                rows.append((n, digest(body), tags))
        except Exception as exc:
            errors.append((n['path'], str(exc)))
        progress(i + 1, len(targets))
    return rows, errors


def apply(rows, note_store, doc_index, progress, cancelled):
    done, skipped, errors = 0, 0, []
    for i, (n, before, tags) in enumerate(rows):
        if cancelled():
            break
        try:
            body = n.read()
            if digest(body) != before:
                skipped += 1  # 미리보기 뒤 내용이 바뀌었으면 다시 분석하도록 남겨 둔다.
            elif isinstance(n, docs.Doc):
                if doc_index.set_annot(n['path'], add_tags=tags):
                    done += 1
                else:
                    skipped += 1
            else:
                existing = {t.casefold() for t in note_tags(body)}
                for tag in tags:
                    if tag.casefold() not in existing:
                        body, _ = add_tag(body, tag)
                        existing.add(tag.casefold())
                if digest(body) != before:
                    note_store.save(n['path'], body, versioned=True, force=True, touch=False, ev='tags')
                    done += 1
        except Exception as exc:
            errors.append((n['path'], str(exc)))
        progress(i + 1, len(rows))
    return done, skipped, errors
