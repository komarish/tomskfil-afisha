import streamlit as st
import requests
from bs4 import BeautifulSoup

# ────────────────── Настройки ──────────────────
AFISHA_URL = "https://tomskfil.ru/afisha/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

st.set_page_config(page_title="Афиша — Томская филармония", page_icon="🎵")


# ────────────────── Парсинг списка афиши ──────────────────
@st.cache_data(show_spinner=False)
def fetch_afisha():
    """Возвращает список событий с главной страницы афиши."""
    resp = requests.get(AFISHA_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    events = []
    for card in soup.select(".poster__card"):
        title_el = card.select_one(".poster__card-title")
        date_el = card.select_one(".poster__card-date-date")
        label_el = card.select_one(".poster__card-label")
        price_el = card.select_one(".poster__card-price-price")
        link_el = card.select_one(".link__more")

        if not title_el or not link_el:
            continue

        # Цена: если элемента нет — берём текст из подписи (например «Бесплатно»)
        if price_el:
            price = price_el.get_text(strip=True)
        else:
            # На некоторых карточках вместо цены — «Бесплатно» или «Только онлайн»
            sub_el = card.select_one(".poster__card-label")
            price = "Бесплатно" if not label_el else "—"

        events.append({
            "title": title_el.get_text(strip=True),
            "date": date_el.get_text(strip=True) if date_el else "—",
            "venue": label_el.get_text(strip=True) if label_el else "—",
            "price": price,
            "url": link_el["href"],
        })

    return events


# ────────────────── Парсинг страницы подробностей ──────────────────
@st.cache_data(show_spinner=False)
def fetch_event_detail(url):
    """Возвращает детали события со страницы 'Узнать подробнее'."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    detail = {
        "title": "",
        "date": "",
        "venue": "",
        "price": "",
        "description": "",
        "buy_url": "",
        "image_url": "",
    }

    # Заголовок
    title_el = soup.select_one("h1") or soup.select_one(".event__title")
    if title_el:
        detail["title"] = title_el.get_text(strip=True)

    # Дата — ищем по характерному шаблону «дата | время»
    for span in soup.select("span"):
        text = span.get_text(strip=True)
        if "|" in text and any(m in text.lower() for m in
                              ["январ", "феврал", "март", "апрел", "май", "июн",
                               "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]):
            detail["date"] = text
            break

    # Место проведения
    for el in soup.select(".poster__card-label, .event__label, .event-label"):
        detail["venue"] = el.get_text(strip=True)
        break

    # Цена
    for el in soup.select(".poster__card-price-price, .event__price"):
        detail["price"] = el.get_text(strip=True)
        break
    if not detail["price"]:
        for span in soup.select("span"):
            text = span.get_text(strip=True)
            if "руб." in text and "Стоимость" not in text:
                detail["price"] = text
                break

    # Ссылка на покупку билета
    buy_el = soup.select_one("a[href*='kupit-bilet'], a:has(span:contains('Купить билет'))")
    if buy_el and buy_el.get("href"):
        detail["buy_url"] = buy_el["href"]
    else:
        # Запасной вариант — ищем любую ссылку с текстом «Купить билет»
        for a in soup.find_all("a"):
            if "Купить билет" in a.get_text():
                detail["buy_url"] = a.get("href", "")
                break

    # Описание — основной текстовый блок
    # Пытаемся найти содержательный абзац (не меню, не подвал)
    desc_parts = []
    for p in soup.select("p"):
        text = p.get_text(strip=True)
        # Отсекаем короткие служебные строки и навигацию
        if len(text) < 40:
            continue
        if any(skip in text for skip in [
            "Томская филармония", "Приёмная", "Кассы", "Наш адрес",
            "Связь с нами", "Главная", "Афиша", "Купить билет",
            "Мы используем куки", "Госуслуги", "Пушкинская карта",
        ]):
            continue
        desc_parts.append(text)

    detail["description"] = "\n\n".join(desc_parts) if desc_parts else "Описание не найдено."

    # Изображение
    img_el = soup.select_one(".event__image img, .poster-detail__img img, article img")
    if img_el and img_el.get("src"):
        detail["image_url"] = img_el["src"]

    return detail


# ────────────────── Интерфейс ──────────────────
st.title("🎵 Афиша Томской филармонии")

col_list, col_detail = st.columns([1, 1], gap="large")

# ── Левая колонка: список событий ──
with col_list:
    st.subheader("События")

    if st.button("🔄 Обновить афишу", use_container_width=True):
        st.cache_data.clear()

    # Загружаем данные (кэш сработает, если уже был запрос)
    try:
        events = fetch_afisha()
    except Exception as e:
        st.error(f"Не удалось загрузить афишу: {e}")
        events = []

    # Список как radio-кнопки — клик выбирает элемент
    if events:
        # Формируем подписи для списка
        labels = [
            f"{ev['title']} — {ev['date']} — {ev['venue']} — {ev['price']}"
            for ev in events
        ]
        selected_idx = st.radio(
            "Выберите событие:",
            range(len(labels)),
            format_func=lambda i: labels[i],
            index=None,  # ничего не выбрано по умолчанию
            label_visibility="collapsed",
        )
    else:
        st.info("Нажмите «Обновить афишу», чтобы загрузить события.")
        selected_idx = None

# ── Правая колонка: подробности ──
with col_detail:
    st.subheader("Подробности")

    if selected_idx is not None:
        event = events[selected_idx]

        with st.spinner("Загружаем подробности…"):
            try:
                detail = fetch_event_detail(event["url"])
            except Exception as e:
                st.error(f"Не удалось загрузить подробности: {e}")
                detail = None

        if detail:
            # Изображение (если есть)
            if detail["image_url"]:
                st.image(detail["image_url"], use_container_width=True)

            # Основные данные
            st.markdown(f"### {detail['title'] or event['title']}")

            meta_cols = st.columns(3)
            meta_cols[0].markdown(f"**📅 Дата**\n\n{detail['date'] or event['date']}")
            meta_cols[1].markdown(f"**📍 Место**\n\n{detail['venue'] or event['venue']}")
            meta_cols[2].markdown(f"**💰 Цена**\n\n{detail['price'] or event['price']}")

            # Описание
            st.markdown("---")
            st.markdown(detail["description"])

            # Кнопка покупки
            if detail["buy_url"]:
                st.link_button(
                    "🎟️ Купить билет",
                    detail["buy_url"],
                    use_container_width=True,
                )

            # Ссылка на оригинальную страницу
            st.caption(f"[Открыть на сайте филармонии]({event['url']})")
        else:
            st.warning("Не удалось получить данные.")
    else:
        st.info("← Выберите событие из списка, чтобы увидеть подробности.")
