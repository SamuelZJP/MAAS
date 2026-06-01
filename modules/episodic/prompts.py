# 情节记忆专用提示词模板（Jinja2 格式，由 prompt_utils.render_prompt 渲染）

# 摘要生成提示词：让 LLM 为一组回合生成事件标题和摘要
EPISODE_SUMMARY_PROMPT = """
你是一个专业的剧情摘要生成器。现在请以第三人称的旁观者视角为下一组对话回合生成一个事件摘要。

请注意，自机主角为{{user}}，因此剧情文本中提到的"我"均为{{user}}。

上下文包含供你参考的关于世界信息和重要角色的最新状态。

## 上下文
{{ context.extra }}

{% if archived_last_round %}
## 已归档的最后一个对话回合（跨事件边界的桥接上下文）
[回合{{ archived_last_round.round_id }}摘要] {{ archived_last_round.summary }}
[回合{{ archived_last_round.round_id }}用户] {{ archived_last_round.user_input }}
[回合{{ archived_last_round.round_id }}AI] {{ archived_last_round.ai_response }}

注意：这个回合位于上一事件的结尾，但其中可能存在当前事件的开头信息。生成当前事件摘要时，请忽略它里面属于上一事件的内容，只把其中属于当前事件的部分当作参考。
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
1. 为这组回合生成一个简短的事件标题（不超过20字），这个标题应当是对事件的高度浓缩信息，体现事件最关键的情节或冲突
2. 生成一段**详略得当**的事件摘要，包含关键情节，可保留重要细节

额外要求：
- 最后一个回合明确存在事件边界，因此如果已经出现下一事件的开头信息，必须忽略那部分内容，不要把它写入当前事件摘要。
- 如果已归档的最后一个对话回合中包含当前事件的开头信息，需要加入，但不要把其中属于上一事件的内容写入当前事件摘要。
- 以第三人称旁观者视角描述事件，不得在末尾添加任何评价、推测、预演或总结。

## 事件摘要格式
起始时间(yyyy/mm/dd)-终止时间(yyyy/mm/dd)—地点
用约200~300字的**一段话**概括上述所有对话回合

## 输出格式
仅输出一个JSON对象：
{"title": "事件标题", "summary": "事件摘要内容"}
"""
