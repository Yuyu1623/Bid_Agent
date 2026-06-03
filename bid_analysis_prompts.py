# 招标文件分析PROMPT设计，包含项目概述提取、技术评分项提取、资格审查项提取、报价细则提取的系统提示和用户提示模板，
# 以及构建消息和调用LLM的函数。

# -*- coding: utf-8 -*-
from typing import Any, Dict, Iterable, List


PROJECT_OVERVIEW_SYSTEM_PROMPT = """你是一个专业的标书撰写专家。请分析用户发来的招标文件，提取并总结项目概述信息。

请重点关注以下方面：
1. 项目名称和基本信息
2. 项目背景和目的
3. 项目类别（服务类，货物类，工程类）和服务年限
4. 项目规模和预算
5. 项目时间安排
6. 项目要实施的具体内容
7. 主要技术特点
8. 其他关键要求

工作要求：
1. 保持提取信息的全面性和准确性，尽量使用原文内容，不要自己编写
2. 只关注与项目实施有关的内容，不提取商务信息
3. 直接返回整理好的项目概述，除此之外不返回任何其他内容
4. 关于项目背景和目的，如果文档中没有明确描述，可以结合调用Google搜索工具以及招标文件上下文进行分析整理"""

PROJECT_OVERVIEW_USER_PROMPT_TEMPLATE = """请分析以下招标文件内容，提取项目概述信息：
{file_content}"""


TECHNICAL_SCORING_SYSTEM_PROMPT = """你是一名专业的招标文件分析师，擅长从复杂的招标文档中高效提取“技术评分项”相关内容。请严格按照以下步骤和规则执行任务：
### 1. 目标定位
- 重点识别文档中与“技术评分”、“评标方法”、“评分标准”、“技术参数”、“技术要求”、“技术方案”、“技术部分”或“评审要素”相关的章节（如“第X章 评标方法”或“附件X：技术评分表”）。
- 忽略商务、价格、资质等非技术类评分项。
### 2. 提取内容要求
对每一项技术评分项，按以下结构化格式输出（若信息缺失，标注“未提及”），如果评分项不够明确，你需要根据上下文分析并也整理成如下格式：
【评分项名称】：<原文描述，保留专业术语>
【权重/分值】：<具体分值或占比，如“30分”或“40%”>
【评分标准】：<详细规则，如“≥95%得满分，每低1%扣0.5分”>
【数据来源】：<文档中的位置，如“第5.2.3条”或“附件3-表2”>

### 3. 处理规则
- **模糊表述**：有些招标文件格式不是很标准，没有明确的“技术评分表”，但一定都会有“技术评分”相关内容，请根据上下文判断评分项。
- **表格处理**：若评分项以表格形式呈现，按行提取，并标注“[表格数据]”。
- **分层结构**：若存在二级评分项（如“技术方案→子项1、子项2”），用缩进或编号体现层级关系。
- **单位统一**：将所有分值统一为“分”或“%”，并注明原文单位（如原文为“20点”则标注“[原文：20点]”）。

### 4. 输出示例
【评分项名称】：系统可用性
【权重/分值】：25分
【评分标准】：年平均故障时间≤1小时得满分；每增加1小时扣2分，最高扣10分。
【数据来源】：附件4-技术评分细则（第3页）

【评分项名称】：响应时间
【权重/分值】：15分 [原文：15%]
【评分标准】：≤50ms得满分；每增加10ms扣1分。
【数据来源】：第6.1.2条

### 5. 验证步骤
提取完成后，执行以下自检：
- [ ] 所有技术评分项是否覆盖（无遗漏）？
- [ ] 权重总和是否与文档声明的技术分总分一致（如“技术部分共60分”）？

直接返回提取结果，除此之外不输出任何其他内容"""


TECHNICAL_SCORING_USER_PROMPT_TEMPLATE = """请分析以下招标文件内容，提取技术评分要求信息：
{file_content}"""


def build_project_overview_messages(file_content: str) -> List[Dict[str, str]]:
    """Build chat messages for extracting a bid project's overview."""
    return [
        {"role": "system", "content": PROJECT_OVERVIEW_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": PROJECT_OVERVIEW_USER_PROMPT_TEMPLATE.format(
                file_content=file_content.strip()
            ),
        },
    ]


def build_project_overview_messages_from_sections(
    sections: Iterable[Any],
) -> List[Dict[str, str]]:
    """Build project overview messages from parsed bid document sections."""
    file_content = sections_to_file_content(sections)
    return build_project_overview_messages(file_content)


def build_technical_scoring_messages(file_content: str) -> List[Dict[str, str]]:
    """Build chat messages for extracting technical scoring requirements."""
    return [
        {"role": "system", "content": TECHNICAL_SCORING_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": TECHNICAL_SCORING_USER_PROMPT_TEMPLATE.format(
                file_content=file_content.strip()
            ),
        },
    ]


def build_technical_scoring_messages_from_sections(
    sections: Iterable[Any],
) -> List[Dict[str, str]]:
    """Build technical scoring messages from parsed bid document sections."""
    file_content = sections_to_file_content(sections)
    return build_technical_scoring_messages(file_content)


def extract_project_overview(file_content: str, llm_client: Any) -> str:
    """Extract project overview from raw bid document text with an LLM client."""
    return llm_client.think(build_project_overview_messages(file_content)) or ""


def extract_project_overview_from_sections(sections: Iterable[Any], llm_client: Any) -> str:
    """Extract project overview from parsed bid document sections with an LLM client."""
    messages = build_project_overview_messages_from_sections(sections)
    return llm_client.think(messages) or ""


def extract_technical_scoring_requirements(file_content: str, llm_client: Any) -> str:
    """Extract technical scoring requirements from raw bid document text."""
    return llm_client.think(build_technical_scoring_messages(file_content)) or ""


def extract_technical_scoring_requirements_from_sections(
    sections: Iterable[Any],
    llm_client: Any,
) -> str:
    """Extract technical scoring requirements from parsed bid document sections."""
    messages = build_technical_scoring_messages_from_sections(sections)
    return llm_client.think(messages) or ""


QUALIFICATION_COMPLIANCE_SYSTEM_PROMPT = """你是一名专业的招标文件分析师，擅长从复杂的招标文档中提取“资格审查”和“符合性审查”相关评分、审查项和否决项。请严格按照以下要求执行：

### 1. 目标定位
- 重点识别与“资格审查”、“资格性审查”、“符合性审查”、“响应性审查”、“初步评审”、“资格条件”、“实质性响应”、“无效投标”、“废标条款”、“否决投标”、“符合性评审表”等相关章节。
- 重点关注投标人必须满足的门槛条件、证明材料、响应要求、否决条件和审查结论标准。
- 不提取技术评分细则和价格评分细则，除非它们同时属于资格/符合性审查要求。

### 2. 提取内容要求
对每一项资格或符合性审查要求，按以下结构化格式输出（若信息缺失，标注“未提及”）：
【审查类别】：<资格审查/符合性审查/响应性审查/初步评审/废标项等>
【审查项名称】：<原文描述，保留专业术语>
【审查要求】：<必须满足的条件、材料、格式、签章、授权、资质、业绩、承诺等>
【判定标准】：<通过/不通过、合格/不合格、是否导致无效投标或废标>
【需提供材料】：<营业执照、资质证书、授权书、承诺函、证明文件等，未提及则写“未提及”>
【数据来源】：<文档中的位置，如“第3.1.2条”或“资格审查表第2项”>

### 3. 处理规则
- 若审查项以表格形式呈现，按行提取，并标注“[表格数据]”。
- 若审查项属于一票否决或废标条款，必须明确标注“[否决项]”。
- 若存在多级结构，请用编号或缩进体现层级。
- 保持原文准确性，不自行编写不存在的条件。

直接返回提取结果，除此之外不输出任何其他内容"""


QUALIFICATION_COMPLIANCE_USER_PROMPT_TEMPLATE = """请分析以下招标文件内容，提取资格审查和符合性审查评分/审查细则：
{file_content}"""


PRICE_SCORING_SYSTEM_PROMPT = """你是一名专业的招标文件分析师，擅长从招标文件中提取“价格评分”或“报价评分”相关规则。请严格按照以下要求执行：

### 1. 目标定位
- 重点识别与“价格评分”、“报价评分”、“价格分”、“商务报价”、“评标基准价”、“评标价”、“投标报价”、“价格权重”、“价格计算公式”、“低价优先法”、“综合评分法价格部分”等相关章节。
- 忽略技术评分、资格审查、符合性审查等非价格评分项。

### 2. 提取内容要求
对每一项价格评分规则，按以下结构化格式输出（若信息缺失，标注“未提及”）：
【评分项名称】：<价格评分/报价评分/评标价计算/价格扣分项等>
【权重/分值】：<具体分值或占比，如“30分”或“40%”>
【计算公式】：<评标基准价、报价得分公式、偏离率计算方式等>
【评分标准】：<低于/高于基准价如何扣分、是否保留小数、异常低价处理等>
【报价要求】：<最高限价、预算金额、报价范围、分项报价、不可竞争费用等>
【数据来源】：<文档中的位置，如“第5.3条”或“价格评分表第1项”>

### 3. 处理规则
- 若价格评分以表格形式呈现，按行提取，并标注“[表格数据]”。
- 若存在不同报价类型或分包报价，请分项列出。
- 若存在最高限价、预算价、控制价、评标基准价生成规则，必须提取。
- 保持公式和数值的原文准确性，不自行补写不存在的算法。

直接返回提取结果，除此之外不输出任何其他内容"""


PRICE_SCORING_USER_PROMPT_TEMPLATE = """请分析以下招标文件内容，提取价格评分细则和报价评分规则：
{file_content}"""


def build_qualification_compliance_messages(file_content: str) -> List[Dict[str, str]]:
    """Build chat messages for extracting qualification/compliance review requirements."""
    return [
        {"role": "system", "content": QUALIFICATION_COMPLIANCE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": QUALIFICATION_COMPLIANCE_USER_PROMPT_TEMPLATE.format(
                file_content=file_content.strip()
            ),
        },
    ]


def build_qualification_compliance_messages_from_sections(
    sections: Iterable[Any],
) -> List[Dict[str, str]]:
    """Build qualification/compliance review messages from parsed sections."""
    file_content = sections_to_file_content(sections)
    return build_qualification_compliance_messages(file_content)


def build_price_scoring_messages(file_content: str) -> List[Dict[str, str]]:
    """Build chat messages for extracting price scoring requirements."""
    return [
        {"role": "system", "content": PRICE_SCORING_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": PRICE_SCORING_USER_PROMPT_TEMPLATE.format(
                file_content=file_content.strip()
            ),
        },
    ]


def build_price_scoring_messages_from_sections(
    sections: Iterable[Any],
) -> List[Dict[str, str]]:
    """Build price scoring messages from parsed sections."""
    file_content = sections_to_file_content(sections)
    return build_price_scoring_messages(file_content)


def extract_qualification_compliance_requirements(file_content: str, llm_client: Any) -> str:
    """Extract qualification/compliance review requirements from raw document text."""
    return llm_client.think(build_qualification_compliance_messages(file_content)) or ""


def extract_qualification_compliance_requirements_from_sections(
    sections: Iterable[Any],
    llm_client: Any,
) -> str:
    """Extract qualification/compliance review requirements from parsed sections."""
    messages = build_qualification_compliance_messages_from_sections(sections)
    return llm_client.think(messages) or ""


def extract_price_scoring_requirements(file_content: str, llm_client: Any) -> str:
    """Extract price scoring requirements from raw document text."""
    return llm_client.think(build_price_scoring_messages(file_content)) or ""


def extract_price_scoring_requirements_from_sections(
    sections: Iterable[Any],
    llm_client: Any,
) -> str:
    """Extract price scoring requirements from parsed sections."""
    messages = build_price_scoring_messages_from_sections(sections)
    return llm_client.think(messages) or ""


def sections_to_file_content(sections: Iterable[Any]) -> str:
    """Pack parsed sections into one document text for LLM analysis."""
    return "\n\n".join(_section_to_markdown(section) for section in sections).strip()


def _section_to_markdown(section: Any) -> str:
    if isinstance(section, dict):
        title = str(section.get("title") or "").strip()
        markdown = str(section.get("markdown") or section.get("content") or "").strip()
    else:
        title = str(getattr(section, "title", "") or "").strip()
        markdown = str(
            getattr(section, "markdown", "") or getattr(section, "content", "")
        ).strip()

    if markdown.startswith("#") or not title:
        return markdown
    return f"## {title}\n{markdown}".strip()
# 这个脚本负责整理招标文件分析时发给大模型的提示词。
