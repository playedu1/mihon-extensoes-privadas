package eu.kanade.tachiyomi.extension.pt.blitztoons

import eu.kanade.tachiyomi.source.model.FilterList
import eu.kanade.tachiyomi.source.model.MangasPage
import eu.kanade.tachiyomi.source.model.Page
import eu.kanade.tachiyomi.source.model.SChapter
import eu.kanade.tachiyomi.source.model.SManga
import eu.kanade.tachiyomi.source.model.SMangaUpdate
import keiyoushi.annotation.Source
import keiyoushi.network.get
import keiyoushi.network.rateLimit
import keiyoushi.source.KeiSource
import keiyoushi.utils.asJsoup
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.jsoup.nodes.Document
import org.jsoup.nodes.Element
import java.net.URLEncoder
import java.text.Normalizer

/** Protótipo independente; somente conteúdo público, sem desbloquear áreas restritas. */
@Source
abstract class BlitzToons : KeiSource() {

    override fun OkHttpClient.Builder.configureClient(): OkHttpClient.Builder = rateLimit(2)

    override suspend fun getPopularManga(page: Int): MangasPage = catalog(page, "populares")

    override suspend fun getLatestUpdates(page: Int): MangasPage = catalog(page, "recentes")

    private suspend fun catalog(page: Int, order: String): MangasPage {
        val document = client.get("$baseUrl/obras?ordem=$order&p=$page").asJsoup()
        return parseCatalog(document, page)
    }

    override suspend fun getSearchMangaList(
        page: Int,
        query: String,
        filters: FilterList,
    ): MangasPage {
        if (query.isBlank()) return getPopularManga(page)
        // Ainda é necessário validar a chave HTTP de busca no site real.
        val encoded = URLEncoder.encode(query, "UTF-8")
        val document = client.get("$baseUrl/obras?busca=$encoded&p=$page").asJsoup()
        val result = parseCatalog(document, page)
        val matches = result.mangas.filter { normalize(it.title).contains(normalize(query)) }
        return MangasPage(matches, result.hasNextPage)
    }

    private fun parseCatalog(document: Document, page: Int): MangasPage {
        val mangas = document.select("a[href*='/obra/']")
            .mapNotNull(::catalogManga)
            .distinctBy { it.url }

        if (mangas.isEmpty()) {
            throw IllegalStateException("BlitzToons: catálogo sem obras, site indisponível ou layout alterado.")
        }
        val nextPage = page + 1
        val hasNext = document.select("a[href*='p=']").any { anchor ->
            runCatching { anchor.absUrl("href").toHttpUrl().queryParameter("p")?.toIntOrNull() == nextPage }
                .getOrDefault(false)
        }
        return MangasPage(mangas, hasNext)
    }

    private fun catalogManga(anchor: Element): SManga? {
        val path = anchor.absUrl("href")
            .takeIf { it.startsWith("$baseUrl/obra/") }
            ?.removePrefix(baseUrl)
            ?: return null
        val cover = anchor.selectFirst("img") ?: anchor.parent()?.selectFirst("img")
        val heading = anchor.selectFirst("h3, h2") ?: anchor.parent()?.selectFirst("h3, h2")
        val titleText = heading?.text().orEmpty()
            .ifBlank { cover?.attr("alt").orEmpty().removePrefix("Capa de ") }
            .ifBlank { anchor.text() }
            .trim()
        if (titleText.isEmpty()) return null
        return SManga.create().apply {
            url = path
            title = titleText
            thumbnail_url = cover?.imageSource()
        }
    }

    override suspend fun getMangaByUrl(url: HttpUrl): SManga? {
        if (url.host != baseUrl.toHttpUrl().host || !url.encodedPath.startsWith("/obra/")) return null
        val manga = SManga.create().apply { this.url = url.encodedPath }
        return fetchMangaUpdate(manga, emptyList(), fetchDetails = true, fetchChapters = false).manga
    }

    override suspend fun fetchMangaUpdate(
        manga: SManga,
        chapters: List<SChapter>,
        fetchDetails: Boolean,
        fetchChapters: Boolean,
    ): SMangaUpdate {
        val document = client.get(getMangaUrl(manga)).asJsoup()
        val details = manga.apply {
            if (fetchDetails) {
                title = document.selectFirst("h1")?.text() ?: title.ifBlank { url.substringAfterLast('/') }
                thumbnail_url = document.selectFirst("img[alt^='Capa de']")?.imageSource() ?: thumbnail_url
                val heading = document.selectFirst("h2:containsOwn(Sinopse), h3:containsOwn(Sinopse)")
                description = heading?.nextElementSibling()?.text()?.takeIf { it.isNotBlank() }
                    ?: heading?.parent()?.select("p")?.joinToString("\n") { it.text() }?.takeIf { it.isNotBlank() }
                    ?: description
                val info = document.body().text().lowercase()
                status = when {
                    info.contains("status completo") || info.contains("status concluído") -> SManga.COMPLETED
                    info.contains("status em lançamento") -> SManga.ONGOING
                    info.contains("status hiato") -> SManga.ON_HIATUS
                    else -> SManga.UNKNOWN
                }
            }
        }

        val chapterList = if (fetchChapters) {
            document.select("a[href*='/ler/']")
                .mapNotNull { anchor ->
                    val relative = anchor.absUrl("href").removePrefix(baseUrl)
                    if (!relative.startsWith("/ler/")) return@mapNotNull null
                    val name = anchor.text().trim()
                    if (!chapterRegex.containsMatchIn(name)) return@mapNotNull null
                    SChapter.create().apply {
                        url = relative
                        this.name = name
                        chapter_number = chapterNumberRegex.find(name)?.groupValues?.get(1)
                            ?.replace(',', '.')?.toFloatOrNull() ?: -1f
                    }
                }
                .distinctBy { it.url }
                .sortedByDescending { it.chapter_number }
        } else {
            chapters
        }

        if (chapterList.isEmpty() && fetchChapters) {
            throw IllegalStateException("BlitzToons: capítulos não encontrados ou restritos.")
        }
        return SMangaUpdate(details, chapterList)
    }

    override suspend fun getPageList(chapter: SChapter): List<Page> {
        val document = client.get(getChapterUrl(chapter)).asJsoup()
        val images = document.select("img[alt^='Página ']")
            .mapNotNull { it.imageSource() }
            .filter { it.startsWith("https://") }
            .distinct()
        if (images.isEmpty()) {
            throw IllegalStateException("BlitzToons: páginas indisponíveis ou capítulo exige login.")
        }
        return images.mapIndexed { index, image -> Page(index, document.location(), image) }
    }

    override fun imageRequest(page: Page): Request = super.imageRequest(page)
        .newBuilder()
        .header("Referer", page.url)
        .build()

    private fun Element.imageSource(): String? {
        val src = listOf("data-src", "data-original", "src", "srcset")
            .map { attr(it).substringBefore(',').trim().substringBefore(' ') }
            .firstOrNull { it.startsWith("https://") || it.startsWith("/") }
            ?: return null
        return when {
            src.startsWith("//") -> "https:$src"
            src.startsWith("/") -> "$baseUrl$src"
            else -> src
        }
    }

    private fun normalize(input: String) = Normalizer.normalize(input, Normalizer.Form.NFD)
        .replace(diacritics, "").lowercase()

    companion object {
        private val chapterRegex = Regex("Capítulo\\s+\\d+(?:[,.]\\d+)?", RegexOption.IGNORE_CASE)
        private val chapterNumberRegex = Regex("(\\d+(?:[,.]\\d+)?)")
        private val diacritics = Regex("\\p{Mn}+")
    }
}
