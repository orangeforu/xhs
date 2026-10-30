"""绘制模板发布全流程示意图。

这些图是原创流程示意，不是剪映界面截图，也不包含任何平台商标或素材。
输出目录非空时拒绝运行，避免覆盖已有证据；需要重画请先手动改名或归档。
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CASE = Path(__file__).resolve().parents[1]
OUT_DIR = CASE / "guides" / "20261029"

FONT_REGULAR = Path("C:/Windows/Fonts/msyh.ttc")
FONT_BOLD = Path("C:/Windows/Fonts/msyhbd.ttc")

INK = "#1F2937"
MUTED = "#4B5563"
LIGHT = "#F3F4F6"
PAPER = "#FAFAF8"
LINE = "#D1D5DB"
TEAL = "#0F766E"
TEAL_LIGHT = "#CCFBF1"
ORANGE = "#C2410C"
ORANGE_LIGHT = "#FFEDD5"
RED = "#B91C1C"
RED_LIGHT = "#FEE2E2"
BLUE = "#1D4ED8"
BLUE_LIGHT = "#DBEAFE"
AMBER = "#B45309"
AMBER_LIGHT = "#FEF3C7"


@dataclass(frozen=True)
class ImageSpec:
    filename: str
    purpose: str


SPECS = (
    ImageSpec("01_publish_route.png", "九步发布路线与两个平台门槛"),
    ImageSpec("02_timeline_14s.png", "正式卡A的14秒时间线与六个替换槽"),
    ImageSpec("03_layer_stack.png", "背景、照片、装饰、文字、网格与音频分层"),
    ImageSpec("04_slot_config_mock.png", "模板配置页应只开放P1—P6六个照片槽"),
    ImageSpec("05_five_inputs.png", "五输入验收的输入、观察点与失败处理"),
    ImageSpec("06_review_loop.png", "提交、审核、驳回修正与公开判定"),
)


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    if not path.is_file():
        raise FileNotFoundError(f"缺少中文字体：{path}")
    return ImageFont.truetype(str(path), size=size)


def canvas(width: int, height: int) -> Image.Image:
    return Image.new("RGB", (width, height), PAPER)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        if char == "\n":
            lines.append(current)
            current = ""
            continue
        candidate = current + char
        if draw.textlength(candidate, font=fnt) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = char
    if current or not lines:
        lines.append(current)
    return lines


def paragraph(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    *,
    fill: str = INK,
    max_width: int = 420,
    spacing: int = 8,
    align: str = "left",
    line_height: int | None = None,
) -> int:
    x, y = xy
    lines = wrap(draw, text, fnt, max_width)
    step = line_height or (fnt.size + spacing)
    for index, line in enumerate(lines):
        if align == "center":
            draw.text((x + max_width / 2, y + index * step), line, font=fnt, fill=fill, anchor="ma")
        else:
            draw.text((x, y + index * step), line, font=fnt, fill=fill)
    return len(lines) * step


def title(draw: ImageDraw.ImageDraw, text: str, subtitle: str, *, width: int) -> None:
    draw.text((60, 42), text, font=font(42, bold=True), fill=INK)
    paragraph(draw, (60, 104), subtitle, font(21), fill=MUTED, max_width=width - 120, spacing=4)


def rounded(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    fill: str,
    outline: str | None = None,
    width: int = 2,
    radius: int = 18,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: str = MUTED,
    width: int = 3,
    head: int = 12,
) -> None:
    draw.line((start, end), fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    if x1 == x2:
        direction = 1 if y2 > y1 else -1
        draw.polygon(
            [(x2, y2), (x2 - head, y2 - direction * head), (x2 + head, y2 - direction * head)],
            fill=color,
        )
    elif y1 == y2:
        direction = 1 if x2 > x1 else -1
        draw.polygon(
            [(x2, y2), (x2 - direction * head, y2 - head), (x2 - direction * head, y2 + head)],
            fill=color,
        )
    else:
        draw.line((start, end), fill=color, width=width)


def badge(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    fill: str,
    text_fill: str = "#FFFFFF",
    size: int = 18,
    padding: int = 10,
) -> tuple[int, int]:
    fnt = font(size, bold=True)
    x, y = xy
    width = int(draw.textlength(text, font=fnt)) + padding * 2
    height = size + padding * 2 - 2
    draw.rounded_rectangle((x, y, x + width, y + height), radius=height // 2, fill=fill)
    draw.text((x + width / 2, y + height / 2), text, font=fnt, fill=text_fill, anchor="mm")
    return x + width, y + height


def step_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    number: int,
    heading: str,
    body: str,
    *,
    gate: bool = False,
    checkpoint: str = "",
) -> None:
    x1, y1, x2, y2 = box
    fill = RED_LIGHT if gate else "#FFFFFF"
    outline = RED if gate else TEAL
    rounded(draw, box, fill=fill, outline=outline, width=3)
    draw.ellipse((x1 + 22, y1 + 20, x1 + 66, y1 + 64), fill=RED if gate else TEAL)
    draw.text((x1 + 44, y1 + 42), str(number), font=font(22, bold=True), fill="#FFFFFF", anchor="mm")
    draw.text((x1 + 82, y1 + 22), heading, font=font(25, bold=True), fill=INK)
    paragraph(draw, (x1 + 24, y1 + 82), body, font(19), fill=MUTED, max_width=x2 - x1 - 48, spacing=5)
    if checkpoint:
        badge(draw, (x1 + 22, y2 - 44), checkpoint, fill=ORANGE if not gate else RED, size=16, padding=9)
    if gate:
        badge(draw, (x2 - 120, y2 - 44), "平台门槛", fill=RED, size=16, padding=9)


def image_route() -> Image.Image:
    width, height = 1600, 1180
    image = canvas(width, height)
    draw = ImageDraw.Draw(image)
    title(
        draw,
        "模板发布全流程：9 步走到公开",
        "红色是平台门槛，绿色是你能控制的部分；每一步都留截图检查点。流程为原创示意，不是剪映界面截图。",
        width=width,
    )

    cards = [
        (60, 150, 520, 380),
        (570, 150, 1030, 380),
        (1080, 150, 1540, 380),
        (1080, 455, 1540, 685),
        (570, 455, 1030, 685),
        (60, 455, 520, 685),
        (60, 760, 520, 990),
        (570, 760, 1030, 990),
        (1080, 760, 1540, 990),
    ]
    steps = [
        ("权限门 M1", "在 App 或专业版找到创作中心／发布模板入口；记录七项准入，不买代开。", True, "截图 A"),
        ("发布面探针", "用 A0 或 14 秒 6 图小样，打开配置页看字段；不提交、不公开。", False, "截图 B"),
        ("素材与授权", "6 张自有／获准照片＋自制背景；字体登记；首版不加音乐。", False, "素材台账"),
        ("正式卡 A", "14 秒：开场 1.2s＋P1—P5 各 2s＋P6 1.6s＋收尾 1.2s。", False, "工程预览"),
        ("配置替换槽", "只把 P1—P6 设为可替换；背景、文字、网格全部固定。", False, "截图 C"),
        ("五输入验收", "竖图、横图、偏主体、明暗差、4／8 张，逐一在模板预览里换。", False, "截图 D"),
        ("填写发布信息", "标题、说明、真实封面、分类；没有 M2 就选免费，不写付费承诺。", False, "截图 E"),
        ("提交审核", "本人点提交；记录提交时间与状态，提交成功不等于已公开。", True, "截图 F"),
        ("公开可搜到", "审核通过＋未登录／另一设备能搜到／打开＋别人能换图；再记账和观察。", False, "截图 G"),
    ]
    for box, (heading, body, gate, checkpoint), number in zip(cards, steps, range(1, 10), strict=True):
        step_card(draw, box, number, heading, body, gate=gate, checkpoint=checkpoint)

    arrow(draw, (520, 265), (570, 265))
    arrow(draw, (1030, 265), (1080, 265))
    arrow(draw, (1310, 380), (1310, 455))
    arrow(draw, (1080, 570), (1030, 570))
    arrow(draw, (570, 570), (520, 570))
    arrow(draw, (290, 685), (290, 760))
    arrow(draw, (520, 875), (570, 875))
    arrow(draw, (1030, 875), (1080, 875))

    rounded(draw, (60, 1015, 1540, 1150), fill=AMBER_LIGHT, outline=AMBER, width=2)
    draw.text((84, 1032), "五条硬规则", font=font(22, bold=True), fill=AMBER)
    rules = [
        "1. 提交成功 ≠ 已公开；只有审核通过且能公开打开才算。",
        "2. 导出 MP4 ≠ 模板；模板必须有可替换的照片槽。",
        "3. 没有替换设置就截图停，不改工程文件或装插件硬做。",
        "4. 被驳回只改一处再交，最多两次；不要原样重复提交。",
        "5. 审核时限由平台决定，不承诺当天通过或一定通过。",
    ]
    for index, rule in enumerate(rules):
        column = index % 2
        row = index // 2
        draw.text((84 + column * 730, 1068 + row * 26), rule, font=font(17), fill=INK)
    return image


def image_timeline() -> Image.Image:
    width, height = 1800, 760
    image = canvas(width, height)
    draw = ImageDraw.Draw(image)
    title(
        draw,
        "正式卡 A：14 秒时间线与替换范围",
        "只有 P1—P6 是用户可替换的照片槽；开场、收尾和文字固定。示意图不是剪映界面截图。",
        width=width,
    )

    left, right = 90, 1710
    span = right - left
    total = 14.0

    def x(seconds: float) -> int:
        return int(left + span * seconds / total)

    segments = [
        (0.0, 1.2, "开场\n1.2s", LIGHT, INK, "固定"),
        (1.2, 3.2, "P1\n2.0s", TEAL_LIGHT, INK, "可替换"),
        (3.2, 5.2, "P2\n2.0s", TEAL_LIGHT, INK, "可替换"),
        (5.2, 7.2, "P3\n2.0s", TEAL_LIGHT, INK, "可替换"),
        (7.2, 9.2, "P4\n2.0s", TEAL_LIGHT, INK, "可替换"),
        (9.2, 11.2, "P5\n2.0s", TEAL_LIGHT, INK, "可替换"),
        (11.2, 12.8, "P6\n1.6s", TEAL_LIGHT, INK, "可替换"),
        (12.8, 14.0, "收尾\n1.2s", AMBER_LIGHT, INK, "固定"),
    ]
    bar_top, bar_bottom = 220, 350
    for start, end, label, fill, text_fill, _ in segments:
        x1, x2 = x(start), x(end)
        draw.rectangle((x1 + 2, bar_top, x2 - 2, bar_bottom), fill=fill, outline="#9CA3AF", width=1)
        draw.multiline_text(((x1 + x2) / 2, (bar_top + bar_bottom) / 2), label, font=font(20, bold=True),
                            fill=text_fill, anchor="mm", align="center", spacing=4)

    for tick in range(15):
        tx = x(tick)
        draw.line((tx, bar_bottom + 8, tx, bar_bottom + 24), fill=MUTED, width=2)
        draw.text((tx, bar_bottom + 30), f"{tick}s", font=font(16), fill=MUTED, anchor="ma")

    draw.text((left, 178), "主轨：8 段连续、不留空隙", font=font(18), fill=MUTED)

    slot_top, slot_bottom = 455, 515
    draw.text((left, 418), "模板替换范围", font=font(18, bold=True), fill=ORANGE)
    for start, end, _, _, _, state in segments:
        x1, x2 = x(start), x(end)
        fill = ORANGE_LIGHT if state == "可替换" else "#E5E7EB"
        draw.rectangle((x1 + 2, slot_top, x2 - 2, slot_bottom), fill=fill, outline="#9CA3AF", width=1)
        draw.text(((x1 + x2) / 2, (slot_top + slot_bottom) / 2), state, font=font(16, bold=True),
                  fill=ORANGE if state == "可替换" else MUTED, anchor="mm")

    notes = [
        "总长 14.0 秒；P1—P5 各 2.0 秒，P6 为 1.6 秒，比前五张短，不再加速。",
        "收尾 2×3 网格必须引用同一组 P1—P6；若平台不能联动替换，改用 A-Lite：去掉网格，收尾只留背景＋祝福语。",
        "不要把 6 张示例照片烘焙进网格——用户替换后网格还是示例图，属于失败模板。",
        "文字只保留开场「一岁一礼」与结尾「愿你岁岁欢喜」，中间六张不加逐图文字。",
    ]
    y = 565
    for note in notes:
        draw.ellipse((left, y + 8, left + 10, y + 18), fill=ORANGE)
        paragraph(draw, (left + 24, y), note, font(19), fill=INK, max_width=width - left - 120, spacing=3)
        y += 42
    return image


def image_layers() -> Image.Image:
    width, height = 1600, 980
    image = canvas(width, height)
    draw = ImageDraw.Draw(image)
    title(
        draw,
        "模板的六层结构：用户只能替换照片层",
        "从下往上叠；背景、装饰、文字、网格和音频都固定或留空。示意图不是剪映界面截图。",
        width=width,
    )

    layers = [
        ("背景层", "原创纯色／渐变；固定，不开放替换", "#E5E7EB", MUTED),
        ("照片层", "P1—P6 共 6 个独立槽；只开放这一层", ORANGE_LIGHT, ORANGE),
        ("装饰层", "边框、角标、细线；固定，不压脸", "#E0F2FE", BLUE),
        ("文字层", "开场与结尾两句；默认固定，不承诺可改", TEAL_LIGHT, TEAL),
        ("收尾网格", "引用 P1—P6；平台不支持联动就删掉", AMBER_LIGHT, AMBER),
        ("音频层", "首版留空；没有可核验授权就不加音乐", "#F3E8FF", "#6B21A8"),
    ]
    base_y = 800
    slab_height = 92
    gap = 16
    left, right = 130, 1080
    for index, (name, note, fill, accent) in enumerate(layers):
        y2 = base_y - index * (slab_height + gap)
        y1 = y2 - slab_height
        draw.rounded_rectangle((left + 14, y1 + 12, right + 14, y2 + 12), radius=14, fill="#E5E7EB")
        draw.rounded_rectangle((left, y1, right, y2), radius=14, fill=fill, outline=accent, width=3)
        draw.rectangle((left, y1 + 12, left + 12, y2 - 12), fill=accent)
        draw.text((left + 34, y1 + 16), f"{index + 1}. {name}", font=font(24, bold=True), fill=INK)
        draw.text((left + 34, y1 + 52), note, font=font(18), fill=MUTED)

    legend_x = 1150
    rounded(draw, (legend_x, 200, 1530, 380), fill="#FFFFFF", outline=LINE, width=2)
    draw.text((legend_x + 24, 220), "图例", font=font(22, bold=True), fill=INK)
    draw.rectangle((legend_x + 24, 266, legend_x + 48, 290), fill=ORANGE_LIGHT, outline=ORANGE, width=2)
    draw.text((legend_x + 60, 264), "可替换：仅照片槽", font=font(18), fill=INK)
    draw.rectangle((legend_x + 24, 312, legend_x + 48, 336), fill="#E5E7EB", outline=MUTED, width=2)
    draw.text((legend_x + 60, 310), "固定：背景／文字／装饰", font=font(18), fill=INK)

    rounded(draw, (1150, 410, 1530, 620), fill=RED_LIGHT, outline=RED, width=2)
    draw.text((legend_x + 24, 430), "发布前必查", font=font(22, bold=True), fill=RED)
    paragraph(
        draw,
        (legend_x + 24, 472),
        "用户视角只看到 6 个照片位。多开一个背景槽、少开一个照片槽，都算配置错误。",
        font(18),
        fill=INK,
        max_width=330,
        spacing=4,
    )

    rounded(draw, (130, 860, 1530, 935), fill=AMBER_LIGHT, outline=AMBER, width=2)
    draw.text((154, 880), "顺序不要反：先有工程层，再在模板配置页标记替换；不要在导出后的 MP4 上点“替换”。",
              font=font(19, bold=True), fill=AMBER)
    return image


def image_slot_config() -> Image.Image:
    width, height = 1600, 1000
    image = canvas(width, height)
    draw = ImageDraw.Draw(image)
    title(
        draw,
        "模板配置页：只勾 P1—P6 六个照片槽",
        "字段名可能是“替换片段素材”“可替换素材”等；以你实际页面为准。示意图不是剪映界面截图。",
        width=width,
    )

    phone_x, phone_y, phone_w, phone_h = 90, 190, 360, 660
    draw.rounded_rectangle((phone_x, phone_y, phone_x + phone_w, phone_y + phone_h), radius=28,
                           fill="#111827", outline="#111827", width=2)
    screen_x, screen_y = phone_x + 24, phone_y + 30
    screen_w, screen_h = phone_w - 48, phone_h - 60
    draw.rectangle((screen_x, screen_y, screen_x + screen_w, screen_y + screen_h), fill="#FDF2F8")
    draw.rectangle((screen_x + 20, screen_y + 80, screen_x + screen_w - 20, screen_y + 430),
                   fill=ORANGE_LIGHT, outline=ORANGE, width=3)
    draw.text((screen_x + screen_w / 2, screen_y + 255), "P3", font=font(64, bold=True), fill=ORANGE, anchor="mm")
    draw.text((screen_x + 20, screen_y + 445), "用户替换后的画面", font=font(16), fill=MUTED)
    for row in range(2):
        for col in range(3):
            gx = screen_x + 30 + col * 92
            gy = screen_y + 490 + row * 34
            draw.rectangle((gx, gy, gx + 82, gy + 26), fill="#FFFFFF", outline=LINE, width=1)
    draw.text((screen_x + 20, screen_y + 570), "收尾网格：引用同一组 P1—P6", font=font(15), fill=MUTED)

    panel_x1, panel_y1, panel_x2, panel_y2 = 520, 185, 1530, 920
    rounded(draw, (panel_x1, panel_y1, panel_x2, panel_y2), fill="#FFFFFF", outline=LINE, width=2)
    draw.text((panel_x1 + 28, panel_y1 + 24), "模板配置（示意）", font=font(26, bold=True), fill=INK)
    draw.text((panel_x1 + 28, panel_y1 + 64), "主轨片段与替换设置", font=font(17), fill=MUTED)
    draw.line((panel_x1 + 28, panel_y1 + 96, panel_x2 - 28, panel_y1 + 96), fill=LINE, width=2)

    rows = [
        ("1", "背景", "0—1.2s", "固定", False),
        ("2", "P1 照片", "1.2—3.2s", "可替换", True),
        ("3", "P2 照片", "3.2—5.2s", "可替换", True),
        ("4", "P3 照片", "5.2—7.2s", "可替换", True),
        ("5", "P4 照片", "7.2—9.2s", "可替换", True),
        ("6", "P5 照片", "9.2—11.2s", "可替换", True),
        ("7", "P6 照片", "11.2—12.8s", "可替换", True),
        ("8", "收尾网格", "12.8—14.0s", "固定（引用 P1—P6）", False),
        ("9", "文字·开场", "0—1.2s", "固定", False),
        ("10", "文字·结尾", "12.8—14.0s", "固定", False),
    ]
    row_y = panel_y1 + 110
    row_h = 60
    for number, name, time_range, state, replaceable in rows:
        fill = ORANGE_LIGHT if replaceable else "#F9FAFB"
        draw.rectangle((panel_x1 + 28, row_y, panel_x2 - 28, row_y + row_h - 6), fill=fill)
        draw.text((panel_x1 + 44, row_y + 18), number, font=font(18, bold=True), fill=MUTED)
        draw.text((panel_x1 + 84, row_y + 14), name, font=font(21, bold=True), fill=INK)
        draw.text((panel_x1 + 330, row_y + 18), time_range, font=font(18), fill=MUTED)
        if replaceable:
            draw.rounded_rectangle((panel_x1 + 620, row_y + 12, panel_x1 + 650, row_y + 42), radius=6,
                                   fill=ORANGE)
            draw.line((panel_x1 + 628, row_y + 27, panel_x1 + 635, row_y + 34, panel_x1 + 646, row_y + 18),
                      fill="#FFFFFF", width=4)
            badge(draw, (panel_x1 + 665, row_y + 10), "可替换", fill=ORANGE, size=16, padding=9)
        else:
            draw.ellipse((panel_x1 + 620, row_y + 14, panel_x1 + 646, row_y + 40), fill="#D1D5DB")
            draw.rectangle((panel_x1 + 627, row_y + 23, panel_x1 + 639, row_y + 32), fill="#374151")
            badge(draw, (panel_x1 + 665, row_y + 10), state, fill="#6B7280", size=16, padding=9)
        row_y += row_h

    rounded(draw, (520, 935, 1530, 985), fill=RED_LIGHT, outline=RED, width=2)
    draw.text((544, 949), "只开放 P1—P6。找不到替换设置就截图停，不修改工程文件、不装插件硬做。",
              font=font(18, bold=True), fill=RED)
    return image


def image_five_inputs() -> Image.Image:
    width, height = 1800, 800
    image = canvas(width, height)
    draw = ImageDraw.Draw(image)
    title(
        draw,
        "五输入验收：别人换成自己的照片也能用",
        "在模板预览里逐项替换；没有预览就先在普通工程手动换图，并如实记录测到哪一层。示意图不是剪映界面截图。",
        width=width,
    )

    cards = [
        ("1", "六张竖图", "标准路径", "看顺序、节奏、收尾是否完整。", "通过／失败"),
        ("2", "六张横图", "裁切", "主体是否被切；必要时提示只用竖图。", "通过／失败"),
        ("3", "主体偏左／右", "出框", "推近后主体是否越界。", "通过／失败"),
        ("4", "一暗一亮", "可读性", "文字与边框是否仍清楚。", "通过／失败"),
        ("5", "4 张或 8 张", "异常输入", "是否错位、空槽、重复；必须有处理。", "通过／失败"),
    ]
    card_w, card_h = 320, 500
    gap = 25
    start_x = 50
    top = 180
    for index, (number, heading, tag, body, result) in enumerate(cards):
        x1 = start_x + index * (card_w + gap)
        x2 = x1 + card_w
        y1, y2 = top, top + card_h
        rounded(draw, (x1, y1, x2, y2), fill="#FFFFFF", outline=TEAL, width=3)
        draw.text((x1 + 24, y1 + 20), number, font=font(28, bold=True), fill=TEAL)
        badge(draw, (x2 - 108, y1 + 22), tag, fill=TEAL, size=15, padding=8)
        draw.text((x1 + 24, y1 + 66), heading, font=font(23, bold=True), fill=INK)

        icon_y = y1 + 112
        if index == 0:
            for row in range(2):
                for col in range(3):
                    gx = x1 + 40 + col * 78
                    gy = icon_y + row * 58
                    draw.rectangle((gx, gy, gx + 62, gy + 44), fill=TEAL_LIGHT, outline=TEAL, width=2)
        elif index == 1:
            for row in range(2):
                for col in range(3):
                    gx = x1 + 34 + col * 82
                    gy = icon_y + row * 54
                    draw.rectangle((gx, gy, gx + 72, gy + 36), fill=BLUE_LIGHT, outline=BLUE, width=2)
        elif index == 2:
            draw.rectangle((x1 + 36, icon_y, x1 + 284, icon_y + 120), fill="#F9FAFB", outline=LINE, width=2)
            draw.ellipse((x1 + 54, icon_y + 38, x1 + 106, icon_y + 90), fill=AMBER_LIGHT, outline=AMBER, width=2)
            draw.ellipse((x1 + 206, icon_y + 38, x1 + 258, icon_y + 90), fill=AMBER_LIGHT, outline=AMBER, width=2)
            draw.line((x1 + 128, icon_y + 64, x1 + 186, icon_y + 64), fill=AMBER, width=3)
        elif index == 3:
            draw.rectangle((x1 + 36, icon_y, x1 + 154, icon_y + 120), fill="#374151")
            draw.rectangle((x1 + 166, icon_y, x1 + 284, icon_y + 120), fill="#FEF9C3")
            draw.text((x1 + 95, icon_y + 60), "暗", font=font(26, bold=True), fill="#FFFFFF", anchor="mm")
            draw.text((x1 + 225, icon_y + 60), "亮", font=font(26, bold=True), fill=AMBER, anchor="mm")
        else:
            for row in range(2):
                for col in range(3):
                    gx = x1 + 46 + col * 70
                    gy = icon_y + row * 54
                    draw.rectangle((gx, gy, gx + 56, gy + 40), fill="#E5E7EB", outline=MUTED, width=2)
            draw.line((x1 + 218, icon_y + 30, x1 + 270, icon_y + 100), fill=RED, width=5)
            draw.line((x1 + 270, icon_y + 30, x1 + 218, icon_y + 100), fill=RED, width=5)

        paragraph(draw, (x1 + 24, y1 + 250), body, font(18), fill=MUTED, max_width=card_w - 48, spacing=4)
        draw.line((x1 + 24, y2 - 96, x2 - 24, y2 - 96), fill=LINE, width=1)
        draw.text((x1 + 24, y2 - 78), result, font=font(19, bold=True), fill=ORANGE)
        draw.text((x1 + 24, y2 - 46), "失败：先修；修不动就写限制", font=font(15), fill=MUTED)
        draw.text((x1 + 24, y2 - 24), "不把未测项写成通过", font=font(15), fill=RED)

    rounded(draw, (50, 710, 1750, 770), fill=AMBER_LIGHT, outline=AMBER, width=2)
    draw.text((74, 726), "测试用自有或明确获准的照片；不组织亲友刷量。测试使用量在台账标“含测试”，不当自然需求证据。",
              font=font(18, bold=True), fill=AMBER)
    return image


def image_review_loop() -> Image.Image:
    width, height = 1800, 900
    image = canvas(width, height)
    draw = ImageDraw.Draw(image)
    title(
        draw,
        "提交之后的判定：通过、驳回、下架",
        "审核由平台控制，时限未知；只有“通过＋公开可打开＋别人能替换”才算发布完成。示意图不是剪映界面截图。",
        width=width,
    )

    top_boxes = [
        ("提交审核", "本人操作；记录时间与状态", BLUE_LIGHT, BLUE),
        ("审核中", "等待；不重复提交、不刷催", LIGHT, MUTED),
        ("审核通过", "状态通过，但仍需检查公开可见", TEAL_LIGHT, TEAL),
        ("公开可访问", "未登录／另一设备能搜到并打开", "#DCFCE7", "#15803D"),
        ("记录与观察", "D0／D3／D7／D14 追加快照", AMBER_LIGHT, AMBER),
    ]
    box_w, box_h = 300, 170
    gap = 50
    start_x = 50
    top = 210
    centers = []
    for index, (heading, body, fill, accent) in enumerate(top_boxes):
        x1 = start_x + index * (box_w + gap)
        x2 = x1 + box_w
        rounded(draw, (x1, top, x2, top + box_h), fill=fill, outline=accent, width=3)
        draw.text((x1 + 24, top + 24), heading, font=font(24, bold=True), fill=INK)
        paragraph(draw, (x1 + 24, top + 70), body, font(17), fill=MUTED, max_width=box_w - 48, spacing=4)
        centers.append((x1 + box_w / 2, top + box_h / 2))
        if index < len(top_boxes) - 1:
            arrow(draw, (x2, top + box_h / 2), (x2 + gap, top + box_h / 2))

    draw.text((60, 420), "分支路径", font=font(20, bold=True), fill=RED)
    reject_box = (390, 480, 760, 650)
    fix_box = (850, 480, 1220, 650)
    down_box = (1310, 480, 1680, 650)
    rounded(draw, reject_box, fill=RED_LIGHT, outline=RED, width=3)
    draw.text((414, 502), "驳回", font=font(24, bold=True), fill=RED)
    draw.text((414, 548), "读原因并归类：", font=font(17), fill=INK)
    draw.text((414, 578), "版权／低质／替换／标题／资格", font=font(17), fill=INK)
    rounded(draw, fix_box, fill=AMBER_LIGHT, outline=AMBER, width=3)
    draw.text((874, 502), "只改一处，再交", font=font(23, bold=True), fill=AMBER)
    paragraph(draw, (874, 548), "保留修改前后截图；最多两次，仍不过就停，不原样重复提交。",
              font(17), fill=INK, max_width=320, spacing=4)
    rounded(draw, down_box, fill=RED_LIGHT, outline=RED, width=3)
    draw.text((1334, 502), "已公开后被下架", font=font(23, bold=True), fill=RED)
    paragraph(draw, (1334, 548), "按通知整改或申诉；不删除证据，不换号重发同一作品。",
              font(17), fill=INK, max_width=320, spacing=4)

    arrow(draw, (500, 380), (500, 480))
    draw.text((512, 410), "不通过", font=font(16, bold=True), fill=RED)
    arrow(draw, (650, 565), (850, 565))
    draw.line((1035, 480, 1035, 405), fill=AMBER, width=3)
    draw.line((1035, 405, 650, 405), fill=AMBER, width=3)
    arrow(draw, (650, 405), (650, 380), color=AMBER)
    draw.text((820, 408), "改完重新提交", font=font(16, bold=True), fill=AMBER)
    arrow(draw, (1230, 300), (1310, 530), color=RED)
    draw.text((1250, 390), "下架", font=font(16, bold=True), fill=RED)

    rounded(draw, (50, 730, 1750, 845), fill="#FFFFFF", outline=LINE, width=2)
    draw.text((74, 750), "三个“不算”", font=font(21, bold=True), fill=INK)
    draw.text((74, 790), "提交成功不算公开　·　审核中不算公开　·　只有自己可见不算公开", font=font(19), fill=RED)
    draw.text((74, 818), "公开后 48 小时内做两个基线：未登录搜索可见性、抖音作品流是否生成；数据缺失就留空，不填 0。",
              font=font(16), fill=MUTED)
    return image


def write_manifest(results: list[tuple[ImageSpec, Image.Image, Path]]) -> None:
    tz = timezone(timedelta(hours=8))
    entries = []
    for spec, image, path in results:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append(
            {
                "file": path.name,
                "purpose": spec.purpose,
                "width": image.width,
                "height": image.height,
                "sha256": digest,
            }
        )
    manifest = {
        "generated_at": datetime.now(tz).isoformat(timespec="seconds"),
        "note": "原创流程示意图，不是剪映界面截图；不含平台素材、真人照片、音乐或字体文件。",
        "images": entries,
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    if OUT_DIR.exists() and any(OUT_DIR.iterdir()):
        print(f"输出目录非空，拒绝覆盖：{OUT_DIR}", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    builders = {
        "01_publish_route.png": image_route,
        "02_timeline_14s.png": image_timeline,
        "03_layer_stack.png": image_layers,
        "04_slot_config_mock.png": image_slot_config,
        "05_five_inputs.png": image_five_inputs,
        "06_review_loop.png": image_review_loop,
    }
    results: list[tuple[ImageSpec, Image.Image, Path]] = []
    for spec in SPECS:
        image = builders[spec.filename]()
        path = OUT_DIR / spec.filename
        image.save(path, "PNG", optimize=True)
        results.append((spec, image, path))
        print(f"已生成 {path.name}  {image.width}x{image.height}")
    write_manifest(results)
    print(f"共 {len(results)} 张，manifest 已写入 {OUT_DIR / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
