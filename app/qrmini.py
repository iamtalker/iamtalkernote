"""큐알 행렬 만들기(segno 를 감싼 얇은 함수). matrix(text) → 0/1 의 행 목록"""
import segno


def matrix(text):
    return [list(r) for r in segno.make(text, error="m", micro=False).matrix]
