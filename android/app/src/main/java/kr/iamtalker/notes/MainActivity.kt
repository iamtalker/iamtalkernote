package kr.iamtalker.notes

import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {
    private val model: NotesModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = lightColorScheme(primary = androidx.compose.ui.graphics.Color(0xFF6D4AFF))) {
                Surface(Modifier.fillMaxSize()) { App(model) }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun App(model: NotesModel) {
    var open by remember { mutableStateOf<Note?>(null) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri: Uri? -> if (uri != null) model.pick(uri) }
    val ctx = androidx.compose.ui.platform.LocalContext.current

    val cur = open
    if (cur != null) {
        Editor(cur, onClose = { open = null; model.refresh() })
        return
    }
    var newDialog by remember { mutableStateOf(false) }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("iamtalkernote") },
                actions = {
                    if (model.tree != null) {
                        TextButton(onClick = { model.refresh() }) { Text("새로고침") }
                        TextButton(onClick = { picker.launch(null) }) { Text("폴더") }
                    }
                }
            )
        },
        floatingActionButton = {
            if (model.tree != null) FloatingActionButton(onClick = { newDialog = true }) { Text("+", fontSize = 24.sp) }
        }
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize()) {
            if (model.tree == null) {
                Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("노트 폴더를 골라 주세요", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(8.dp))
                    Text("컴퓨터의 iamtalkernote 와 같은 폴더(동기화 도구로 폰에 받은 폴더)를 고르면 됩니다.", style = MaterialTheme.typography.bodySmall)
                    Spacer(Modifier.height(16.dp))
                    Button(onClick = { picker.launch(null) }) { Text("폴더 고르기") }
                }
                return@Column
            }
            OutlinedTextField(
                value = model.query, onValueChange = { model.query = it }, singleLine = true,
                placeholder = { Text("검색 (공백 = AND)") },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp)
            )
            Row(Modifier.padding(horizontal = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = model.inBody, onCheckedChange = { model.inBody = it; if (it) model.loadBodies() })
                Text("본문까지 검색", style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.weight(1f))
                Text(model.status, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(end = 8.dp))
            }
            if (model.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            val shown = model.results()
            val fmt = remember { SimpleDateFormat("yyyy.MM.dd HH:mm", Locale.KOREA) }
            LazyColumn(Modifier.fillMaxSize()) {
                items(shown, key = { it.uri.toString() }) { n ->
                    Column(Modifier.fillMaxWidth().clickable { open = n }.padding(horizontal = 16.dp, vertical = 10.dp)) {
                        Text(n.title, style = MaterialTheme.typography.bodyLarge, maxLines = 1)
                        Text((if (n.folder.isEmpty()) "" else n.folder + " · ") + fmt.format(Date(n.modified)),
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
                    }
                    HorizontalDivider()
                }
            }
        }
    }
    if (newDialog) {
        var title by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { newDialog = false },
            title = { Text("새 노트") },
            text = { OutlinedTextField(value = title, onValueChange = { title = it }, singleLine = true, placeholder = { Text("제목") }) },
            confirmButton = {
                TextButton(onClick = {
                    newDialog = false
                    model.create(title)?.let { open = it }
                }) { Text("만들기") }
            },
            dismissButton = { TextButton(onClick = { newDialog = false }) { Text("취소") } }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun Editor(note: Note, onClose: () -> Unit) {
    val ctx = androidx.compose.ui.platform.LocalContext.current
    var text by remember { mutableStateOf<String?>(null) }
    var saved by remember { mutableStateOf("") }
    LaunchedEffect(note.uri) {
        val t = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) { NoteRepo.read(ctx, note.uri) }
        text = t; saved = t
    }
    fun save() {
        val t = text ?: return
        if (t != saved) {
            NoteRepo.write(ctx, note.uri, t)
            saved = t
        }
    }
    BackHandler { save(); onClose() }
    Scaffold(topBar = {
        TopAppBar(
            title = { Text(note.title, maxLines = 1) },
            navigationIcon = { TextButton(onClick = { save(); onClose() }) { Text("←") } },
            actions = { TextButton(onClick = { save() }) { Text("저장") } }
        )
    }) { pad ->
        val t = text
        if (t == null) {
            Box(Modifier.padding(pad).fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        } else {
            BasicTextField(
                value = t, onValueChange = { text = it },
                textStyle = TextStyle(fontSize = 15.sp, lineHeight = 22.sp, color = MaterialTheme.colorScheme.onSurface, fontFamily = FontFamily.Default),
                cursorBrush = SolidColor(MaterialTheme.colorScheme.primary),
                modifier = Modifier.padding(pad).fillMaxSize().padding(16.dp).imePadding()
            )
        }
    }
}
