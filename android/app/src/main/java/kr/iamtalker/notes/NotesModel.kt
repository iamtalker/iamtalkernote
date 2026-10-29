package kr.iamtalker.notes

import android.app.Application
import android.content.Intent
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class NotesModel(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("settings", 0)

    var tree by mutableStateOf<Uri?>(prefs.getString("tree", null)?.let(Uri::parse))
        private set
    var notes by mutableStateOf<List<Note>>(emptyList())
        private set
    var loading by mutableStateOf(false)
        private set
    var status by mutableStateOf("")
        private set
    var query by mutableStateOf("")
    var inBody by mutableStateOf(false)

    /** 본문 검색용 사본(소문자). 파일 크기·수정 시각이 그대로면 다시 읽지 않는다 */
    private val bodies = HashMap<String, Pair<Long, String>>()
    var bodyReady by mutableStateOf(0)
        private set
    private var job: Job? = null

    init {
        if (tree != null) refresh()
    }

    fun pick(uri: Uri) {
        getApplication<Application>().contentResolver.takePersistableUriPermission(
            uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        prefs.edit().putString("tree", uri.toString()).apply()
        tree = uri
        bodies.clear()
        refresh()
    }

    fun refresh() {
        val t = tree ?: return
        job?.cancel()
        job = viewModelScope.launch {
            loading = true
            status = "노트를 찾는 중…"
            val list = withContext(Dispatchers.IO) {
                NoteRepo.scan(getApplication(), t) { n -> status = "노트를 찾는 중… $n" }
            }
            notes = list.sortedByDescending { it.modified }
            status = "노트 ${list.size}개"
            loading = false
        }
    }

    /** 본문 검색을 켰을 때: 아직 읽지 않았거나 바뀐 노트의 본문을 뒤에서 읽어 둔다 */
    fun loadBodies() {
        job?.cancel()
        job = viewModelScope.launch {
            val todo = notes.filter { bodies[it.uri.toString()]?.first != it.modified }
            var done = 0
            withContext(Dispatchers.IO) {
                for (n in todo) {
                    if (n.size in 1..2_000_000) {
                        val text = runCatching { NoteRepo.read(getApplication(), n.uri) }.getOrDefault("")
                        bodies[n.uri.toString()] = n.modified to (n.title + "\n" + text).lowercase()
                    }
                    done++
                    if (done % 100 == 0) status = "본문을 읽는 중… $done/${todo.size}"
                }
            }
            status = "노트 ${notes.size}개"
            bodyReady++
        }
    }

    /** 공백으로 나눈 낱말이 모두 들어 있는 노트(제목, 본문 검색을 켰으면 본문까지) */
    fun results(): List<Note> {
        bodyReady // 본문을 다 읽으면 다시 계산되게
        val words = query.trim().lowercase().split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (words.isEmpty()) return notes
        return notes.filter { n ->
            val hay = if (inBody) bodies[n.uri.toString()]?.second ?: n.title.lowercase() else n.title.lowercase()
            words.all { hay.contains(it) }
        }
    }

    fun create(title: String): Note? {
        val t = tree ?: return null
        val n = NoteRepo.create(getApplication(), t, title) ?: return null
        notes = listOf(n) + notes
        return n
    }
}
