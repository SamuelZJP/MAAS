SEMANTIC_UPDATE_PROMPT = """
## 特别强调
<user>、主角、"我"的名称为{{user}}。请把所有的<user>替换为{{user}}。
## 上下文
<Reference_Info>
{{reference_info}}
</Reference_Info>

## 过去状态
{{current_memory_yaml}}

## 本回合对话
**注意，用户输入也是重要的信息来源**
用户输入：{{user_input}}
AI回复：{{ai_response}}

## 变量更新规则
<Variable_Update_Rules>
{{variable_update_rules}}
</Variable_Update_Rules>

## 输出格式
<Output_Format>
---
变量输出格式:
  rule:
    - you must output the update analysis and the actual update commands in the end of the next reply
    - 'the update commands must strictly follow the **JSON Patch (RFC 6902)** standard, but can only use the following operations: `replace` (replace the value of existing paths); `add` (add a new value to an existing path); `remove` (remove a value from an existing path); that is, the output must be a valid JSON array containing operation objects'
    - don't update field names starts with `_` as they are readonly, such as `_变量`
  format: |-
    <UpdateVariable>
    <Analysis>$(IN ENGLISH, no less than 80 words)
    - ${calculate time passed: ...}
    - ${decide whether dramatic updates are allowed as it's in a special case or the time passed is more than usual: yes/no}
    - ${analyze every variable based on its corresponding `check`, according only to current reply instead of previous plots: ...}
    </Analysis>
    <JSONPatch>
    [
      { "op": "replace", "path": "${/path/to/variable}", "value": "${new_value}" },
      { "op": "add", "path": "${/path/to/dict_key}", "value": "${new_value}" },
      { "op": "add", "path": "${/path/to/list/-}", "value": "${appended_value}" },
      { "op": "add", "path": "${/path/to/list/0}", "value": "${inserted_value}" },
      { "op": "remove", "path": "${/path/to/variable}" },
      ...
    ]
    </JSONPatch>
    </UpdateVariable>
</Output_Format>
"""
