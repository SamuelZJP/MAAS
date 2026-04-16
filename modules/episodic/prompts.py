# 情节记忆专用提示词模板（Jinja2 格式，由 prompt_utils.render_prompt 渲染）

# 召回提示词：让 LLM 从候选事件中筛选与当前对话相关的事件
RECALL_PROMPT = """
你是一个记忆管理助手。当前正在进行一段角色扮演对话，你需要判断哪些历史事件与当前对话相关。

## 当前上下文
{{ recent_rounds_text }}
{{ context.extra }}
男主角、"我"的名称均为周嘉鹏。

## 用户最新输入
{{ context.user_input }}

## 历史事件列表
{% for episode in episodes %}
- 事件{{ episode.episode_id }}：{{ episode.title }}
{% endfor %}

## 任务
从上方的历史事件列表中，选出与当前对话上下文相关或可能有助于未来情节发展的事件。只选择确实有助于AI进行剧情演绎的事件，不要过度召回。

## 输出格式
仅输出一个JSON数组，包含所选事件的ID，例如：[2, 5, 7]
若无相关事件，输出空数组：[]
"""


# 边界检测提示词：让 LLM 判断最新回合是否标志着一个事件的结束
BOUNDARY_DETECT_PROMPT = """
你是一个记忆管理助手。你需要判断以下一系列连续的对话回合中，最新的回合是否标志着一个事件的结束。

## 上下文
{{ context.extra }}
男主角、"我"的名称均为周嘉鹏。

{% if archived_last_round %}
## 已归档的最后一个对话回合（跨事件边界的桥接上下文）
[回合{{ archived_last_round.round_id }}摘要]{{ archived_last_round.summary }}
[回合{{ archived_last_round.round_id }}用户] {{ archived_last_round.user_input }}
[回合{{ archived_last_round.round_id }}AI] {{ archived_last_round.ai_response }}

注意：这个回合位于已归档事件的末尾，但其中已经出现了当前进行中事件的开头信息。判断时请忽略它里面属于上一事件的内容，只把其中属于当前事件的部分当作参考。
{% endif %}

## 待检测的回合摘要（按时间顺序）
{% if include_first_message %}
[首条消息]
{{ first_message_summary }}
{% endif %}

{% for round in unarchived_rounds %}
[回合{{ round.round_id }}]
{{ round.summary }}

{% endfor %}

## 未归档的最后一个对话回合（完整内容）
[回合{{ latest_unarchived_round.round_id }}摘要]
{{ latest_unarchived_round.summary }}

[回合{{ latest_unarchived_round.round_id }}用户]
{{ latest_unarchived_round.user_input }}

[回合{{ latest_unarchived_round.round_id }}AI]
{{ latest_unarchived_round.ai_response }}

## 判断标准
事件边界通常出现在：场景发生显著变化、时间出现明显跳跃、核心话题/冲突发生转折等情况下。
如果所有回合都在讲述同一个连贯的场景或事件，则不存在边界。
注意：当前给出的所有未归档回合都属于同一个待闭合事件，因此你只需要判断最新回合是否使这个事件闭合，不需要指出边界位于哪个回合。

## 输出格式
仅输出一个JSON对象：
- 若不存在边界：{"has_boundary": false}
- 若存在边界：{"has_boundary": true}
"""


# 摘要生成提示词：让 LLM 为一组回合生成事件标题和摘要
EPISODE_SUMMARY_PROMPT = """
你是一个专业的剧情摘要生成器。现在请以第三人称的旁观者视角为下一组对话回合生成一个事件摘要。

请注意，男主角为周嘉鹏，女主角为林清羽，因此剧情文本中的隐晦提到的"对方"均为林清羽，提到的"我"均为周嘉鹏。

上下文包含供你参考的关于世界信息和林清羽的最新状态。

## 上下文
{{ context.extra }}

{% if archived_last_round %}
## 已归档的最后一个对话回合（跨事件边界的桥接上下文）
[回合{{ archived_last_round.round_id }}摘要] {{ archived_last_round.summary }}
[回合{{ archived_last_round.round_id }}用户] {{ archived_last_round.user_input }}
[回合{{ archived_last_round.round_id }}AI] {{ archived_last_round.ai_response }}

注意：这个回合位于上一事件的结尾，但其中已经出现了当前事件的开头信息。生成当前事件摘要时，请忽略它里面属于上一事件的内容，只把其中属于当前事件的部分当作参考。
{% endif %}

## 事件包含的对话回合
{% if include_first_message %}
[首条消息]
{{ first_message_summary }}
{% endif %}

{% for round in rounds_in_range %}
<回合{{ round.round_id }}>
[回合{{ round.round_id }}摘要]
{{ round.summary }}
[回合{{ round.round_id }}用户]
{{ round.user_input }}
[回合{{ round.round_id }}AI]
{{ round.ai_response }}
</回合{{ round.round_id }}>
{% endfor %}

## 任务
1. 为这组回合生成一个简短的事件标题（不超过20字），这个标题应当是事件的最浓缩信息
2. 生成一段事件摘要，应包含关键情节、人物互动和情感变化，保留重要细节但去除冗余

额外要求：
- 最后一个回合明确存在事件边界，因此如果已经出现下一事件的开头信息，必须忽略那部分内容，不要把它写入当前事件摘要。
- 如果已归档的最后一个对话回合中包含当前事件的开头信息，需要加入，但不要把其中属于上一事件的内容写入当前事件摘要。

## 事件摘要格式
起始时间(yyyy/mm/dd hh:mm)-终止时间(yyyy/mm/dd hh:mm)—地点
用约200~300字的**一段话**概括上述所有对话回合，忠实记录关键对白片段、情报、行为和情感变化。直接呈现，不加以解读。
如果事件包含的对话回合很多(超过10个)，你可以自行扩充字数上限，但不得多于500字。

## 输出格式
仅输出一个JSON对象：
{"title": "事件标题", "summary": "事件摘要内容"}
"""
