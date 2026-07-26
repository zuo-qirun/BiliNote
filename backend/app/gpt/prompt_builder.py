from app.gpt.prompt import BASE_PROMPT

note_formats = [
    {'label': '目录', 'value': 'toc'},
    {'label': '原片跳转', 'value': 'link'},
    {'label': '原片截图', 'value': 'screenshot'},
    {'label': 'AI总结', 'value': 'summary'}
]

note_styles = [
    {'label': '精简', 'value': 'minimal'},
    {'label': '详细', 'value': 'detailed'},
    {'label': '学术', 'value': 'academic'},
    {"label": '教程',"value": 'tutorial', },
    {'label': '小红书', 'value': 'xiaohongshu'},
    {'label': '生活向', 'value': 'life_journal'},
    {'label': '任务导向', 'value': 'task_oriented'},
    {'label': '商业风格', 'value': 'business'},
    {'label': '会议纪要', 'value': 'meeting_minutes'},
    {'label': '热梗生成器', 'value': 'meme_generator'}
]


# 生成 BASE_PROMPT 函数
def generate_base_prompt(title, segment_text, tags, _format=None, style=None, extras=None):
    # 生成 Base Prompt 开头部分
    prompt = BASE_PROMPT.format(
        video_title=title,
        segment_text=segment_text,
        tags=tags
    )

    # 添加用户选择的格式
    if _format:
        prompt += "\n" + "\n".join([get_format_function(f) for f in _format])

    # 根据用户选择的笔记风格添加描述
    if style:
        prompt += "\n" + get_style_format(style)

    # 添加额外内容
    if extras:
        prompt += f"\n{extras}"
    return prompt


# 获取格式函数
def get_format_function(format_type):
    format_map = {
        'toc': get_toc_format,
        'link': get_link_format,
        'screenshot': get_screenshot_format,
        'summary': get_summary_format
    }
    return format_map.get(format_type, lambda: '')()


# 风格描述的处理
def get_style_format(style):
    style_map = {
        'minimal': '1. **精简信息**: 仅记录最重要的内容，简洁明了。',
        'detailed': '2. **详细记录**: 包含完整的内容和每个部分的详细讨论。需要尽可能多的记录视频内容，最好详细的笔记',
        'academic': '3. **学术风格**: 适合学术报告，正式且结构化。',
        'xiaohongshu': '''4. **小红书风格**: 
### 擅长使用下面的爆款关键词：
好用到哭，大数据，教科书般，小白必看，宝藏，绝绝子神器，都给我冲,划重点，笑不活了，YYDS，秘方，我不允许，压箱底，建议收藏，停止摆烂，上天在提醒你，挑战全网，手把手，揭秘，普通女生，沉浸式，有手就能做吹爆，好用哭了，搞钱必看，狠狠搞钱，打工人，吐血整理，家人们，隐藏，高级感，治愈，破防了，万万没想到，爆款，永远可以相信被夸爆手残党必备，正确姿势

### 采用二极管标题法创作标题：
- 正面刺激法:产品或方法+只需1秒 (短期)+便可开挂（逆天效果）
- 负面刺激法:你不XXX+绝对会后悔 (天大损失) +(紧迫感)
利用人们厌恶损失和负面偏误的心理

### 写作技巧
1. 使用惊叹号、省略号等标点符号增强表达力，营造紧迫感和惊喜感。
2. **使用emoji表情符号，来增加文字的活力**
3. 采用具有挑战性和悬念的表述，引发读、“无敌者好奇心，例如“暴涨词汇量”了”、“拒绝焦虑”等
4. 利用正面刺激和负面激，诱发读者的本能需求和动物基本驱动力，如“离离原上谱”、“你不知道的项目其实很赚”等
5. 融入热点话题和实用工具，提高文章的实用性和时效性，如“2023年必知”、“chatGPT狂飙进行时”等
6. 描述具体的成果和效果，强调标题中的关键词，使其更具吸引力，例如“英语底子再差，搞清这些语法你也能拿130+”
7. 使用吸引人的标题：''',

        'life_journal': '5. **生活向**: 记录个人生活感悟，情感化表达。',
        'task_oriented': '6. **任务导向**: 强调任务、目标，适合工作和待办事项。',
        'business': '7. **商业风格**: 适合商业报告、会议纪要，正式且精准。',
        'meeting_minutes': '8. **会议纪要**: 适合商业报告、会议纪要，正式且精准。',
        "tutorial":"9.**教程笔记**:尽可能详细的记录教程,特别是关键点和一些重要的结论步骤",
        'meme_generator': '''10. **热梗生成器（封神叙事体）**:
请把视频内容改写成富有张力、适合分享的“高光叙事”笔记。第一行必须以“真拿你们没办法，坐好喽”开场（可接一个合适的表情或逗号），随后用宏大、克制而有画面感的语气讲述事件。

写作结构：
- 先交代人物、场景、背景、压力或长期遗憾，营造“此刻为何重要”；
- 再按视频中的实际过程推进，突出关键对抗、转折、操作或决定；
- 对高潮瞬间使用短句、停顿与细节描写增强节奏；
- 结尾升华坚持、技艺、团队或热爱，但不要空泛重复。

表达要求：可使用“封神、加冕、绝境、破局、载入记忆”等热梗叙事词汇，但须与内容相称；允许用“那一刻、谁也没想到、并非……而是……”等句式，不要机械堆砌。使用 Markdown 标题和自然分段，正文应是一篇完整叙事，不是逐条清单。

事实要求：只能依据原视频/转写提供的人名、时间、比分、数字、结果和事件写作；不得捏造赛事、冠军、战绩、引语、身份、地点或因果关系。信息不足时宁可概括为“视频未交代”，也不要补写。专有名词、代码和数字保持原样。'''
    }
    return style_map.get(style, '')


# 格式化输出内容
def get_toc_format():
    return '''
    9. **目录**: 自动生成一个基于 `##` 级标题的目录。不需要插入原片跳转
    '''


def get_link_format():
    return '''
    10. **原片跳转**: 为每个主要章节添加时间戳，使用格式 `*Content-[mm:ss]`。 
    重要：**始终**在章节标题前加上 `*Content` 前缀，例如：`AI 的发展史 *Content-[01:23]`。一定是标题在前 插入标记在后
    '''


def get_screenshot_format():
    return '''
11. **原片截图**:你收到的截图一般是一个网格，网格的每张图片就是一个时间点，左上角会包含时间mm:ss的格式，请你结合我发你的图片插入截图提示，请你帮助用户更好的理解视频内容，请你认真的分析每个图片和对应的转写文案，插入最合适的内容来备注用户理解，请一定按照这个格式 返回否则系统无法解析：
- 格式：`*Screenshot-[mm:ss]`

    '''


def get_summary_format():
    return '''
    12. **AI总结**: 在笔记末尾加入简短的AI生成总结,并且二级标题 就是 AI 总结 例如 ## AI 总结。
    '''
