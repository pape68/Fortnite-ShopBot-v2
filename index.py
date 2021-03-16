import datetime
import itertools
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, Tuple

import requests
from PIL import Image, ImageDraw

from util import Fonts, ImageUtil, Language


MARGIN_TOP = 150
MARGIN_BOTTOM = 20
MARGIN_LEFT = 20
MARGIN_RIGHT = 20

DOUBLEWIDE_SIZE = (660, 550)
NORMAL_SIZE = (320, 550)
SMALL_SIZE = (260, 260)
X_MARGIN = 25
Y_MARGIN = 100
NAME_HEIGHT = 40
PRICE_HEIGHT = 25
RARITY_HEIGHT = 6
SLOPE = 8
VBUCKS_SLOPE = 15

with open('config.json', encoding='utf-8') as f:
    config = json.load(f)

name_fonts = Fonts([config['fonts']['ja'], -2], [config['fonts']['ko'], -2], [config['fonts']['other'], 0])
langs = map(lambda x: x.name, Language.langs())
if config['lang'] not in langs:
    raise ValueError(f"'lang' value must be one of {langs!r}")


def get_user_facing_flag_images(item: dict) -> list:
    data = []
    user_facing_flag_converter = {
        'HasVariants': {
            'matchMethod': 'full',
            'image': 'variant_variant.png'
        },
        'HasUpgradeQuests': {
            'matchMethod': 'full',
            'image': 'variant_quest.png'
        },
        'Animated': {
            'matchMethod': 'ends',
            'image': 'variant_animated.png'
        },
        'Reactive': {
            'matchMethod': 'starts',
            'image': 'variant_adaptive.png'
        },
        'Traversal': {
            'matchMethod': 'ends',
            'image': 'variant_traversal.png'
        },
        'BuiltInEmote': {
            'matchMethod': 'full',
            'image': 'variant_builtincontent.png'
        },
        'Synced': {
            'matchMethod': 'full',
            'image': 'variant_synced.png'
        },
        'Enlightened': {
            'matchMethod': 'full',
            'image': 'variant_enlightened.png'
        },
        'GearUp': {
            'matchMethod': 'full',
            'image': 'variant_custom.png'
        }
    }
    user_facing_flags = [tag[len('Cosmetics.UserFacingFlags.'):] for tag in item['gameplayTags'] if tag.startswith('Cosmetics.UserFacingFlags.')]
    for user_facing_flag in user_facing_flags:
        for flag, info in user_facing_flag_converter.items():
            if info['matchMethod'] == 'full':
                if user_facing_flag == flag:
                    data.append(info['image'])
            elif info['matchMethod'] == 'starts':
                if user_facing_flag.startswith(flag):
                    data.append(info['image'])
            elif info['matchMethod'] == 'ends':
                if user_facing_flag.endswith(flag):
                    data.append(info['image'])
    return data


def hex_color_to_tuple(color: str) -> tuple:
    if color.startswith('#'):
        color = color[1:]
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))


def get_content(session: Optional[requests.Session] = requests.Session()) -> dict:
    res = session.get('https://fortnitecontent-website-prod07.ol.epicgames.com/content/api/pages/fortnite-game', headers={'Accept-Language': config['lang']})
    if res.status_code != 200:
        print(f'Failed to get shop data\n{res.text}', file=sys.stderr)
        res.raise_for_status()
    return res.json()


def get_section_priority(session: Optional[requests.Session] = requests.Session()) -> list:
    data = get_content(session)
    return [section['sectionId'] for section in data['shopSections']['sectionList']['sections']]


def format_shop(data: dict, session: Optional[requests.Session] = requests.Session()) -> dict:
    priority = get_section_priority(session)
    sections = {}
    for panel in data['shop']:
        if panel['section']['id'] not in sections:
            sections[panel['section']['id']] = {
                'id': panel['section']['id'],
                'name': panel['section']['name'],
                'until': (
                    datetime.datetime.fromisoformat(data['currentRotation'][panel['section']['id']])
                    if panel['section']['id'] in data['currentRotation'] else
                    None
                ),
                'panels': []
            }
        sections[panel['section']['id']]['panels'].append(panel)
    sections = [{'id': v['id'], 'name': v['name'], 'until': v['until'], 'panels': sorted(v['panels'], key=lambda x: x['priority'], reverse=True)}
                for v in sorted(sections.values(), key=lambda x: priority.index(x['id']))]

    return {
        'lastUpdate': data['lastUpdate'],
        'carousel': data['carousel'],
        'sections': sections
    }


def get_shop(session: Optional[requests.Session] = requests.Session()) -> dict:
    res = session.get(
        'https://fortniteapi.io/v2/shop',
        params={'lang': config['lang']},
        headers={'Authorization': config['api_key']}
    )
    if res.status_code != 200:
        print(f'Failed to get shop data\n{res.text}', file=sys.stderr)
        res.raise_for_status()
    return format_shop(res.json(), session)


def get_rarities(session: Optional[requests.Session] = requests.Session()) -> dict:
    res = session.get(
        'https://fortniteapi.io/v2/rarities',
        params={'lang': config['lang']},
        headers={'Authorization': config['api_key']}
    )
    if res.status_code != 200:
        print(f'Failed to get rarities data\n{res.text}', file=sys.stderr)
        res.raise_for_status()
    return res.json()


def get_rarity_colors(session: Optional[requests.Session] = requests.Session()) -> dict:
    rarities = get_rarities(session)
    return {
        rarity['id']: hex_color_to_tuple(rarity['colors']['Color1'])
        for rarity in [*rarities['rarities'], *rarities['series']]
        if rarity['colors'] is not None
    }


def get_size(panel: dict) -> Tuple[int, int]:
    if panel['tileSize'] == 'DoubleWide':
        return DOUBLEWIDE_SIZE
    elif panel['tileSize'] == 'Normal':
        return NORMAL_SIZE
    elif panel['tileSize'] == 'Small':
        return SMALL_SIZE


def get_section_width(section: dict) -> int:
    size = -X_MARGIN
    small_count = 0
    for panel in section['panels']:
        if panel['tileSize'] == 'Small':
            small_count += 1
            if small_count % 2 == 1:
                size += get_size(panel)[0] + X_MARGIN
        else:
            size += get_size(panel)[0] + X_MARGIN
    return size


def get_shop_size(data: dict) -> Tuple[int, int]:
    x_list = []
    y = 0
    for section in data['sections']:
        x_list.append(get_section_width(section))
        if len(section['panels']) == 1 and section['panels'][0]['tileSize'] == 'Small':
            y += Y_MARGIN + SMALL_SIZE[1]
        else:
            y += Y_MARGIN + NORMAL_SIZE[1]
    return MARGIN_LEFT + max(x_list) + MARGIN_RIGHT, MARGIN_TOP + y + MARGIN_BOTTOM


def generate_image(data: dict, colors: dict, session: Optional[requests.Session] = requests.Session()) -> Image.Image:
    print(f"Generating shop image with {len(data['sections'])} sections")
    start = time.time()
    now = datetime.datetime.now(datetime.timezone.utc)
    image = Image.new('RGB', get_shop_size(data), (0, 80, 190))

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(generate_section, section, colors, now, session) for section in data['sections']]
    
    y = MARGIN_TOP
    for future in futures:
        try:
            section_image = future.result()
        except Exception:
            print('Failed to generate section', file=sys.stderr)
            traceback.print_exc()
        else:
            image.paste(section_image, (0, y), section_image)
            y += section_image.height
    end = time.time()
    print(f"Generated shop image in {end - start:.2f} seconds")
    return image


def generate_section(section: dict, colors: dict, now: datetime.datetime, session: Optional[requests.Session] = requests.Session()) -> Image.Image:
    if len(section['panels']) == 1 and section['panels'][0]['tileSize'] == 'Small':
        image = Image.new('RGBA', (MARGIN_LEFT + get_section_width(section) + MARGIN_RIGHT, Y_MARGIN + SMALL_SIZE[1]))
    else:
        image = Image.new('RGBA', (MARGIN_LEFT + get_section_width(section) + MARGIN_RIGHT, Y_MARGIN + NORMAL_SIZE[1]))
    canvas = ImageDraw.Draw(image)

    x = MARGIN_LEFT
    size = 50
    if section['name']:
        fonts = name_fonts.fonts_size(size, size, size)
        x = 50
        final_x, _ = fonts.write_text(canvas, section['name'].upper(), (x, Y_MARGIN // 2 - 25))
        x += final_x
    if section['until'] is not None:
        timer = ImageUtil.ratio_resize(
            ImageUtil.open('shop_timer.png').convert('RGBA'),
            size,
            size
        )
        x += 12
        image.paste(
            timer,
            (x, Y_MARGIN // 2 - 15 - 4),
            timer
        )

        end = section['until'] - now
        m, s = divmod(end.seconds, 60)
        h, m = divmod(m, 60)
        timer_text = (
            "{}:{:0>2}:{:0>2}".format(h, m, s)
            if end > datetime.timedelta(hours=1) else
            "{}:{:0>2}".format(m, s)
        )
        x += timer.width + 6
        fonts = name_fonts.fonts_size(size // 2, size // 2, size // 2)
        _, y = fonts.text_size(timer_text)
        fonts.write_text(
            canvas,
            timer_text,
            (x, Y_MARGIN // 2 - 15 + y // 2),
            fill=(115, 200, 235)
        )

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(generate_panel, panel, colors, session) for panel in section['panels']]

    x = MARGIN_LEFT
    small_count = 0
    for num, future in enumerate(futures):
        try:
            panel_image = future.result()
        except Exception:
            print('Failed to generate panel', file=sys.stderr)
            traceback.print_exc()
        else:
            panel = section['panels'][num]
            size = get_size(panel)
            if panel['tileSize'] == 'Small':
                small_count += 1
                if small_count % 2 == 1:
                    pos = (x, Y_MARGIN)
                    x += size[0] + X_MARGIN
                else:
                    pos = (x - size[0] - X_MARGIN, Y_MARGIN + (NORMAL_SIZE[1] - size[1] * 2) + size[1])
            else:
                pos = (x, Y_MARGIN)
                x += size[0] + X_MARGIN
            image.paste(panel_image, pos)
            if panel['banner'] is not None:
                font_size, minus = name_fonts.fit_fonts_size(
                    image.width - 25,
                    16,
                    panel['banner']['name']
                )
                fonts = name_fonts.fonts_size(font_size, font_size, font_size)
                text_width = fonts.text_size(panel['banner']['name'])[0]
                banner_height = 32
                color = 'red' if panel['banner']['intensity'] == 'Low' else 'yellow'
                banner_rear = ImageUtil.ratio_resize(ImageUtil.open(f'{color}_banner_rear.png').convert('RGBA'), 0, banner_height, resample=Image.BICUBIC)
                banner_middle = ImageUtil.open(f'{color}_banner_middle.png').convert('RGBA').resize((text_width, banner_height))
                banner_front = ImageUtil.ratio_resize(ImageUtil.open(f'{color}_banner_front.png').convert('RGBA'), 0, banner_height, resample=Image.BICUBIC)
                image.paste(
                    banner_rear,
                    (
                        pos[0] - 15,
                        pos[1] - 15
                    ),
                    banner_rear
                )
                image.paste(
                    banner_middle,
                    (
                        pos[0] - 15 + banner_rear.width,
                        pos[1] - 15
                    ),
                    banner_middle
                )
                image.paste(
                    banner_front,
                    (
                        pos[0] - 15 + banner_rear.width + banner_middle.width,
                        pos[1] - 15
                    ),
                    banner_front
                )
                fonts.write_text(
                    canvas,
                    panel['banner']['name'],
                    (pos[0] - 15 + banner_rear.width,
                     pos[1] - 15 + 5),
                    fill=(255, 255, 255) if panel['banner']['intensity'] == 'Low' else (0, 0, 0)
                )

    return image


def generate_panel(panel: dict, colors: dict, session: Optional[requests.Session] = requests.Session()) -> Image.Image:
    image = Image.new('RGB', get_size(panel))
    canvas = ImageDraw.Draw(image)
    image2 = Image.new('RGBA', (image.width * 2, image.height * 2))
    canvas2 = ImageDraw.Draw(image2)
    size = get_size(panel)
    display_asset = ImageUtil.ratio_resize(
        ImageUtil.get_image(panel['displayAssets'][0]['background'], session).convert('RGBA'),
        *size
    )
    image.paste(
        display_asset,
        ImageUtil.center_x(display_asset.width, image.width, 0),
        display_asset
    )

    canvas.polygon(
        ((0, size[1] - PRICE_HEIGHT), (size[0], size[1] - PRICE_HEIGHT),
         (size[0], size[1]), (0, size[1])),
        fill=(14, 14, 14)
    )
    vbucks = ImageUtil.ratio_resize(
        ImageUtil.open('vbucks.png').point(lambda x: x * 0.8).convert('RGBA').rotate(-15),
        40,
        40
    )
    pos = size[0] - vbucks.width - 5
    image.paste(
        vbucks,
        (pos, size[1] - vbucks.height + 10),
        vbucks
    )
    text = f"{panel['price']['finalPrice']:,}"
    fonts = name_fonts.fonts_size(15, 15, 15)
    x, y = fonts.text_size(text)
    pos = pos - x - 3
    fonts.write_text(
        canvas,
        text,
        (pos, size[1] - y - 4),
        fill=(160, 175, 185)
    )

    if panel['price']['finalPrice'] != panel['price']['regularPrice']:
        text = f"{panel['price']['regularPrice']:,}"
        fonts = name_fonts.fonts_size(15, 15, 15)
        x, y = fonts.text_size(text)
        pos = pos - x - 6
        fonts.write_text(
            canvas,
            text,
            (pos, size[1] - y - 4),
            fill=(100, 100, 100)
        )
        canvas2.line(
            (((pos - 2) * 2, (size[1] - y - 4 + 10) * 2), ((pos + x + 3) * 2, (size[1] - y - 4 + 6) * 2)),
            fill=(100, 110, 110),
            width=3 * 2
        )

    canvas2.polygon(
        ((0, (size[1] - PRICE_HEIGHT - NAME_HEIGHT - RARITY_HEIGHT) * 2), (size[0] * 2, (size[1] - PRICE_HEIGHT - NAME_HEIGHT - RARITY_HEIGHT - SLOPE) * 2),
         (size[0] * 2, (size[1] - PRICE_HEIGHT - NAME_HEIGHT - SLOPE) * 2), (0, (size[1] - PRICE_HEIGHT - NAME_HEIGHT) * 2)),
        fill=colors[panel['series']['id'] if panel['series'] is not None else panel['rarity']['id']]
    )
    canvas2.polygon(
        ((0, (size[1] - PRICE_HEIGHT - NAME_HEIGHT) * 2), (size[0] * 2, (size[1] - PRICE_HEIGHT - NAME_HEIGHT - SLOPE) * 2),
         (size[0] * 2, (size[1] - PRICE_HEIGHT) * 2), (0, (size[1] - PRICE_HEIGHT) * 2)),
        fill=(30, 30, 30)
    )
    image2.thumbnail(image.size, Image.LANCZOS)
    image.paste(
        image2,
        (0, 0),
        image2
    )

    fonts = name_fonts.fonts_size(20, 20, 20)
    x, y = fonts.text_size(panel['displayName'])
    fonts.write_text(
        canvas,
        panel['displayName'],
        ImageUtil.center_x(x, image.width, size[1] - PRICE_HEIGHT - y - 10),
        fill=(255, 255, 255)
    )

    icons = [
        ImageUtil.ratio_resize(ImageUtil.open(filename).convert('RGBA'), 30, 30)
        for filename in set(itertools.chain(*[get_user_facing_flag_images(item) for item in panel['granted']]))
    ]
    x = size[0] - 10
    for icon in icons:
        x -= icon.width
        image.paste(
            icon,
            (x, size[1] - PRICE_HEIGHT - NAME_HEIGHT - RARITY_HEIGHT - 15 - icon.height),
            icon
        )
        x -= 10

    return image


def default(obj: Any) -> Any:
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    return obj


session = requests.Session()
print('Getting shop data')
data = get_shop(session)
with open('shop.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False, default=default)
colors = get_rarity_colors(session)
image = generate_image(data, colors, session)
print('Saving image')
start = time.time()
image.save('shop.png')
end = time.time()
print(f'Successfully saved image in {end - start:.2f} seconds')
