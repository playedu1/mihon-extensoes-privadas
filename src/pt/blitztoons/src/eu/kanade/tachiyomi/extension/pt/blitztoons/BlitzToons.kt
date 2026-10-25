package eu.kanade.tachiyomi.extension.pt.blitztoons

import eu.kanade.tachiyomi.source.model.Filter
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
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** Protótipo independente; somente conteúdo público, sem desbloquear áreas restritas. */
@Source
abstract class BlitzToons : KeiSource() {

    override fun OkHttpClient.Builder.configureClient(): OkHttpClient.Builder = rateLimit(2)


    private class CatalogFilter(name: String, val parameter: String, val options: List<Pair<String, String>>) :
        Filter.Select<String>(name, options.map { it.first }.toTypedArray()) {
        val selected: String get() = options[state].second
    }

    override val supportsFilterFetching get() = true

    override suspend fun fetchFilterData(): JsonElement {
        val doc = client.get("$baseUrl/obras").asJsoup()
        val genres = doc.select("a[href*='genero=']")
            .mapNotNull { link ->
                val slug = link.absUrl("href").toHttpUrl().queryParameter("genero") ?: return@mapNotNull null
                val title = link.text().trim().takeIf { it.isNotEmpty() } ?: return@mapNotNull null
                title to slug
            }
            .distinctBy { it.second }
            .sortedBy { it.first.lowercase() }
        return JsonArray(genres.map { (title, slug) ->
            JsonObject(mapOf("title" to JsonPrimitive(title), "slug" to JsonPrimitive(slug)))
        })
    }

    override fun getFilterList(data: JsonElement?): FilterList {
        val remoteGenres = runCatching {
            data?.jsonArray?.map {
                it.jsonObject.getValue("title").jsonPrimitive.content to
                    it.jsonObject.getValue("slug").jsonPrimitive.content
            }.orEmpty()
        }.getOrDefault(emptyList())
        return FilterList(
            CatalogFilter(
                "Categoria",
                "tipo",
                listOf(
                    "Todas" to "", "Comics" to "comic", "Novels" to "novel",
                    "Yaoi" to "yaoi", "Yuri" to "yuri", "Shoujo" to "shoujo",
                ),
            ),
            CatalogFilter(
                "Ordenação",
                "ordem",
                listOf("Recentes" to "recentes", "Populares" to "populares", "Melhor nota" to "nota", "A–Z" to "az"),
            ),
            CatalogFilter(
                "Status",
                "status",
                listOf("Todos" to "", "Em lançamento" to "ongoing", "Completo" to "completed", "Hiato" to "hiatus"),
            ),
            CatalogFilter(
                "Gênero",
                "genero",
                listOf("Todos" to "") + if (remoteGenres.isNotEmpty()) remoteGenres else defaultGenres,
            ),
        )
    }

    override suspend fun getPopularManga(page: Int): MangasPage = catalog(page, "populares")

    override suspend fun getLatestUpdates(page: Int): MangasPage = catalog(page, "recentes")

    private suspend fun catalog(page: Int, order: String): MangasPage {
        val url = "$baseUrl/obras".toHttpUrl().newBuilder()
            .addQueryParameter("ordem", order)
            .addQueryParameter("p", page.toString())
            .build()
        return parseCatalog(client.get(url).asJsoup(), page)
    }

    override suspend fun getSearchMangaList(page: Int, query: String, filters: FilterList): MangasPage {
        val url = "$baseUrl/obras".toHttpUrl().newBuilder()
        query.trim().takeIf { it.isNotEmpty() }?.let { url.addQueryParameter("q", it) }
        filters.filterIsInstance<CatalogFilter>().forEach { filter ->
            filter.selected.takeIf { it.isNotEmpty() }?.let { url.addQueryParameter(filter.parameter, it) }
        }
        url.addQueryParameter("p", page.toString())
        return parseCatalog(client.get(url.build()).asJsoup(), page)
    }

    private fun parseCatalog(doc: Document, page: Int): MangasPage {
        val mangas = doc.select("a[href*='/obra/']:not(.card-cover)")
            .mapNotNull(::catalogManga)
            .distinctBy { it.url }
        val hasNext = doc.select("a[href*='p=']").any { anchor ->
            runCatching {
                anchor.absUrl("href").toHttpUrl().queryParameter("p")?.toIntOrNull() == page + 1
            }.getOrDefault(false)
        }
        return MangasPage(mangas, hasNext)
    }

    private fun catalogManga(anchor: Element): SManga? {
        val path = anchor.absUrl("href")
            .takeIf { it.startsWith("$baseUrl/obra/") }?.removePrefix(baseUrl) ?: return null
        val titleText = anchor.text().trim().takeIf { it.isNotEmpty() } ?: return null
        val cover = (anchor.closest(".card") ?: anchor.parent()?.parent())?.selectFirst("img")
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
        private val defaultGenres = listOf(
            "Ação" to "acao",
            "Aventura" to "aventura",
            "Comédia" to "comedia",
            "Drama" to "drama",
            "Fantasia" to "fantasia",
            "Isekai" to "isekai",
            "Mistério" to "misterio",
            "Romance" to "romance",
            "Sobrenatural" to "sobrenatural",
            "Terror" to "terror",
            "Vingança" to "vinganca",
        )
        private val chapterRegex = Regex("Capítulo\\s+\\d+(?:[,.]\\d+)?", RegexOption.IGNORE_CASE)
        private val chapterNumberRegex = Regex("(\\d+(?:[,.]\\d+)?)")
        private val diacritics = Regex("\\p{Mn}+")
    }
}
