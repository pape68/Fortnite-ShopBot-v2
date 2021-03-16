# -*- coding: utf-8 -*-
import unicodedata
from enum import Enum
from typing import Callable, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont


class Language(Enum):
    ar = 'ar'
    de = 'de'
    en = 'en'
    en_US = 'en'
    en_us = en_US
    es = 'es'
    es_ES = es
    es_es = es_ES
    es_419 = 'es-419'
    es_MX = es_419
    es_mx = es_MX
    fr = 'fr'
    it = 'it'
    ja = 'ja'
    ko = 'ko'
    pl = 'pl'
    pt_BR = 'pt-BR'
    pt_br = pt_BR
    ru = 'ru'
    tr = 'tr'
    zh_CN = 'zh-CN'
    zh_cn = zh_CN
    zh_Hant = 'zh-Hant'
    zh_hant = zh_Hant
    zh = zh_Hant

    @classmethod
    def langs(cls) -> list:
        return list(set(cls))


class Utility:
    @classmethod
    def is_universal(cls, char: str) -> bool:
        try:
            name = unicodedata.name(char)
        except ValueError:
            return True
        if (any([name.startswith(i) for i in ['DIGIT', 'LATIN']])
            or any([i == name for i in ['HYPHEN-MINUS', 'FULL STOP', 'COMMA', 'EXCLAMATION MARK', 'QUESTION MARK',
                                        'COLON', 'SEMICOLON', 'LEFT PARENTHESIS', 'RIGHT PARENTHESIS', 'LOW LINE']])):
            return True
        return False

    @classmethod
    def is_japanese(cls, char: str) -> bool:
        try:
            name = unicodedata.name(char)
        except ValueError:
            return False
        if (any([name.startswith(i) for i in ['CJK UNIFIED', 'HIRAGANA', 'KATAKANA', 'IDEOGRAPHIC', 'FULLWIDTH DIGIT',
                                              'FULLWIDTH LATIN', 'FULLWIDTH COLON', 'FULLWIDTH SEMICOLON',
                                              'FULLWIDTH LEFT PARENTHESIS', 'FULLWIDTH RIGHT PARENTHESIS',
                                              'KATAKANA-HIRAGANA PROLONGED SOUND MARK']])
            or any([i in name for i in ['CORNER BRACKET', 'FULLWIDTH EXCLAMATION MARK', 'FULLWIDTH QUESTION MARK'
                                        'FULLWIDTH LOW LINE']])):
            return True
        return False

    @classmethod
    def is_hangul(cls, char: str) -> bool:
        try:
            name = unicodedata.name(char)
        except ValueError:
            return False
        if name.startswith('HANGUL'):
            return True
        return False


class ImageUtil:
    @classmethod
    def open(cls, filename: str,
             directory: Optional[str] = 'assets/images/') -> Image.Image:
        return Image.open(f'{directory}{filename}')

    @classmethod
    def open_font(cls, size: int, font: str,
                  directory: Optional[str] = 'assets/fonts/',) -> ImageFont.ImageFont:
        return ImageFont.truetype(f'{directory}{font}', size)

    @classmethod
    def get_image(cls, url: str, session: Optional[requests.Session] = requests.Session()) -> Optional[Image.Image]:
        res = session.get(url, stream=True)
        if res.status_code == 200:
            return Image.open(res.raw)
        else:
            return None

    @classmethod
    def ratio_resize(cls, image: Image.Image, max_width: int, max_height: int,
                     func: Optional[Callable] = max, resample: Optional[int] = Image.LANCZOS) -> Image.Image:
        ratio = func(max_width / image.width, max_height / image.height)
        return image.resize((int(image.width * ratio), int(image.height * ratio)), resample)

    @classmethod
    def center_x(cls, foreground_width: int,
                 background_width: int,
                 distanceTop: int = 0) -> tuple:
        return (int(background_width / 2) - int(foreground_width / 2), distanceTop)

    @classmethod
    def fit_fonts_size(cls, image_width: int, fonts: 'Fonts',
                       max_size: int, text: str,
                       preferred: Optional['Language'] = None) -> Tuple[int, int]:
        minus = 1
        for i in reversed(range(1, max_size + 1)):
            minus -= 1
            fontssize = fonts.fonts_size(i, i, i, preferred)
            width = fontssize.text_size(text)[0]
            if width < (image_width - 10):
                return i, minus

    @classmethod
    def text_size(cls, fonts: 'FontsSize',
                  text: str) -> tuple:
        lines_x = []
        text_x, text_y = 0, 0
        line_y = 0
        for char in text:
            if char == '\n':
                lines_x.append(text_x)
                text_x, text_y = (0, text_y + line_y)
                line_y = 0
                continue
            if Utility.is_japanese(char):
                font = fonts.ja
            elif Utility.is_hangul(char):
                font = fonts.ko
            else:
                font = fonts.other
            char_x, char_y = font.getsize(char)
            text_x += char_x
            if text_y < char_y:
                text_y = char_y
            if line_y < char_y:
                line_y = char_y
        final_x = max(lines_x) if lines_x else text_x
        final_y = text_y
        return final_x, final_y

    @classmethod
    def write_text(cls, canvas: ImageDraw.Draw,
                   fonts: 'FontsSize',
                   text: str,
                   pos: Optional[tuple] = (0, 0),
                   *args: list,
                   **kwargs: dict
                   ) -> tuple:
        x, y = pos
        lines_x = []
        text_x, text_y = 0, 0
        line_y = 0
        for char in text:
            if char == '\n':
                lines_x.append(text_x)
                x, y = (pos[0], y + line_y)
                text_x, text_y = (0, text_y + line_y)
                line_y = 0
                continue
            font, y_minus = fonts.detect(char)
            char_x, char_y = canvas.textsize(char, font=font)
            text_x += char_x
            if text_y < char_y:
                text_y = char_y
            if line_y < char_y:
                line_y = char_y
            canvas.text((x, y - y_minus), char, font=font, *args, **kwargs)
            x, y = ((x + char_x), y)
        final_x = max(lines_x) if lines_x else text_x
        final_y = text_y
        return final_x, final_y


class FontsSize:
    __slots__ = ('_ja', '_ja_pos', '_ko', '_ko_pos', '_other', '_other_pos', '_preferred')

    def __init__(self, ja: Tuple[ImageFont.ImageFont, int],
                 ko: Tuple[ImageFont.ImageFont, int],
                 other: Tuple[ImageFont.ImageFont, int],
                 preferred: Optional[Language] = None) -> None:
        self._ja, self._ja_pos = ja
        self._ko, self._ko_pos = ko
        self._other, self._other_pos = other
        self._preferred = preferred

    @property
    def ja(self) -> ImageFont.ImageFont:
        return self._ja

    @property
    def ja_pos(self) -> int:
        return self._ja_pos

    @property
    def ko(self) -> ImageFont.ImageFont:
        return self._ko

    @property
    def ko_pos(self) -> int:
        return self._ko_pos

    @property
    def other(self) -> ImageFont.ImageFont:
        return self._other

    @property
    def other_pos(self) -> int:
        return self._other_pos

    @property
    def preferred(self) -> Optional[Language]:
        return self._preferred

    def detect(self, char: str) -> Tuple[ImageFont.ImageFont, int]:
        if self._preferred and Utility.is_universal(char):
            lang = self._preferred.value if self._preferred.value in ['ja', 'ko'] else 'other'
            return getattr(self, f'_{lang}'), getattr(self, f'_{lang}_pos')
        if Utility.is_japanese(char):
            return self._ja, self._ja_pos
        elif Utility.is_hangul(char):
            return self._ko, self._ko_pos
        else:
            return self._other, self._other_pos

    def text_size(self, text: str) -> tuple:
        return ImageUtil.text_size(self, text)

    def write_text(self, canvas: ImageDraw.Draw,
                   text: str,
                   pos: Optional[tuple] = (0, 0),
                   *args: list,
                   **kwargs: dict) -> tuple:
        return ImageUtil.write_text(canvas, self, text, pos, *args, **kwargs)


class Fonts:
    __slots__ = ('_ja', '_ja_pos', '_ko', '_ko_pos', '_other', '_other_pos')

    def __init__(self, ja: Tuple[str, int], ko: Tuple[str, int], other: Tuple[str, int]) -> None:
        self._ja, self._ja_pos = ja
        self._ko, self._ko_pos = ko
        self._other, self._other_pos = other

    @property
    def ja(self) -> str:
        return self._ja

    @property
    def ja_pos(self) -> int:
        return self._ja_pos

    @property
    def ko(self) -> str:
        return self._ko

    @property
    def ko_pos(self) -> int:
        return self._ko_pos

    @property
    def other(self) -> str:
        return self._other

    @property
    def other_pos(self) -> int:
        return self._other_pos

    def detect(self, char: str) -> Tuple[str, int]:
        if Utility.is_japanese(char):
            return self._ja, self._ja_pos
        elif Utility.is_hangul(char):
            return self._ko, self._ko_pos
        else:
            return self._other, self._other_pos

    def fonts_size(self, ja_size: int, ko_size: int, other_size: int, preferred: Optional[Language] = None) -> FontsSize:
        return FontsSize(
            (ImageUtil.open_font(ja_size, self._ja), self._ja_pos),
            (ImageUtil.open_font(ko_size, self._ko), self._ko_pos),
            (ImageUtil.open_font(other_size, self._other), self._other_pos),
            preferred
        )

    def fit_fonts_size(self, image_width: int, max_size: int, text: str) -> Tuple[int, int]:
        return ImageUtil.fit_fonts_size(image_width, self, max_size, text)
