# -*- coding: utf-8 -*-
"""Prompt builders for bid document analysis."""

from typing import Any, Dict, Iterable, List


PROJECT_OVERVIEW_SYSTEM_PROMPT = """你是专业的招标文件分析师。请从用户提供的招标文件内容中提取“投标人须知/项目概览”信息。

请严格按下面 14 个字段输出，每个字段单独一行，格式为“字段名：内容”。除“是否专门面向中小微企业采购”和“是否为暗标”外，尽量保留招标文件原文表达；没有明确提及则写“未提及”。

1. 项目名称
2. 项目编号
3. 项目类别（服务类，货物类，工程类）和服务年限
4. 包号
5. 项目规模和预算
6. 招标人
7. 招标代理机构
8. 项目所属领域
9. 项目时间安排
10. 项目要实施的具体内容
11. 主要技术特点
12. 其他关键要求
13. 是否专门面向中小微企业采购：只输出“是”或“否”；无法判断则写“未提及”
14. 是否为暗标：只输出“是”或“否”；无法判断则写“未提及”

要求：
- 只提取与项目概览和投标人须知相关的内容。
- 不要编造招标文件没有说明的信息。
- 不要输出解释、分析过程、寒暄或额外标题。"""


PROJECT_OVERVIEW_USER_PROMPT_TEMPLATE = """请分析以下招标文件内容，提取投标人须知/项目概览信息：

{file_content}"""


TECHNICAL_SCORING_SYSTEM_PROMPT = """你是专业的招标文件技术要求分析师。请从招标文件中提取“技术要求”内容，而不是评分表。

重点关注：
- 服务/货物/工程的技术标准、技术参数、功能要求、性能指标
- 实施范围、交付内容、服务要求、运维要求、验收要求
- 对技术方案、人员、设备、工期、质量、安全、保密等方面的要求
- 主要技术特点和必须响应的技术条款

输出要求：
- 使用清晰的小标题和条目整理。
- 尽量保留原文表达，尤其是硬性要求、参数、数值、期限和验收标准。
- 未发现技术要求时写“未提及”。
- 不要输出商务评分、技术评分、价格评分或资格审查内容。"""


TECHNICAL_SCORING_USER_PROMPT_TEMPLATE = """请分析以下招标文件内容，提取技术要求：

{file_content}"""


QUALIFICATION_COMPLIANCE_SYSTEM_PROMPT = """你是专业的招标文件审查条款分析师。请提取“资格审查”内容，并按三个模块输出。

请严格使用以下 Markdown 表格格式输出：

## 资格性审查
| 序号 | 资格要求 | 需提供资料 |
| --- | --- | --- |
| 1 | 原文要求 | 原文要求的证明资料 |

## 符合性审查
| 序号 | 资格要求 | 需提供资料 |
| --- | --- | --- |
| 1 | 原文要求 | 原文要求的证明资料 |

## 废标项
| 序号 | 废标项 | 具体表现 |
| --- | --- | --- |
| 1 | 原文废标/否决条款 | 导致废标或无效投标的具体表现 |

要求：
- 尽量按招标文件原文表达提取，不要自行改写成泛泛表述。
- 资格性审查包括供应商资格、资质、业绩、授权、承诺、财务、纳税、社保、信用等门槛条件。
- 符合性审查包括响应文件格式、签章、报价、有效期、实质性响应等要求。
- 废标项包括无效投标、否决投标、一票否决、重大偏差、实质性不响应等条款。
- 未发现某个模块内容时，该模块仍保留表头，并写一行“未提及”。"""


QUALIFICATION_COMPLIANCE_USER_PROMPT_TEMPLATE = """请分析以下招标文件内容，提取资格性审查、符合性审查和废标项：

{file_content}"""


PRICE_SCORING_SYSTEM_PROMPT = """你是专业的招标文件评分办法分析师。请提取“评分要求”，分为商务评分和技术评分两个模块。

请严格使用以下 Markdown 表格格式输出：

## 商务评分
| 评分项 | 评分标准 | 分数 |
| --- | --- | --- |
| 原文评分项 | 原文评分标准 | 分值 |

## 技术评分
| 评分项 | 评分标准 | 分数 |
| --- | --- | --- |
| 原文评分项 | 原文评分标准 | 分值 |

要求：
- 商务评分通常包括业绩、资质、信誉、人员、服务能力、企业实力、报价以外的商务响应等。
- 技术评分通常包括技术方案、实施方案、服务方案、质量保障、进度安排、应急方案、售后服务等。
- 表格内容尽量保留招标文件原文表达。
- 如果评分项存在子项，请在“评分项”中体现层级关系。
- 不要输出价格评分，除非招标文件把价格评分归入商务评分且无法拆分；此时请在评分项中标明“价格/报价评分”。
- 未发现某个模块内容时，该模块仍保留表头，并写一行“未提及”。"""


PRICE_SCORING_USER_PROMPT_TEMPLATE = """请分析以下招标文件内容，提取商务评分和技术评分要求：

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
    """Build chat messages for extracting technical requirements."""
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
    """Build technical requirement messages from parsed sections."""
    file_content = sections_to_file_content(sections)
    return build_technical_scoring_messages(file_content)


def build_qualification_compliance_messages(file_content: str) -> List[Dict[str, str]]:
    """Build messages for extracting qualification/compliance requirements."""
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
    """Build messages for extracting business and technical scoring."""
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
    """Build scoring requirement messages from parsed sections."""
    file_content = sections_to_file_content(sections)
    return build_price_scoring_messages(file_content)


def extract_project_overview(
    file_content: str,
    llm_client: Any,
    stream_output: bool = True,
) -> str:
    """Extract project overview from raw bid document text."""
    return llm_client.think(
        build_project_overview_messages(file_content),
        stream=stream_output,
    ) or ""


def extract_project_overview_from_sections(
    sections: Iterable[Any],
    llm_client: Any,
    stream_output: bool = True,
) -> str:
    """Extract project overview from parsed bid document sections."""
    messages = build_project_overview_messages_from_sections(sections)
    return llm_client.think(messages, stream=stream_output) or ""


def extract_technical_scoring_requirements(
    file_content: str,
    llm_client: Any,
    stream_output: bool = True,
) -> str:
    """Extract technical requirements from raw bid document text."""
    return llm_client.think(
        build_technical_scoring_messages(file_content),
        stream=stream_output,
    ) or ""


def extract_technical_scoring_requirements_from_sections(
    sections: Iterable[Any],
    llm_client: Any,
    stream_output: bool = True,
) -> str:
    """Extract technical requirements from parsed bid document sections."""
    messages = build_technical_scoring_messages_from_sections(sections)
    return llm_client.think(messages, stream=stream_output) or ""


def extract_qualification_compliance_requirements(
    file_content: str,
    llm_client: Any,
    stream_output: bool = True,
) -> str:
    """Extract qualification/compliance review requirements from raw text."""
    return llm_client.think(
        build_qualification_compliance_messages(file_content),
        stream=stream_output,
    ) or ""


def extract_qualification_compliance_requirements_from_sections(
    sections: Iterable[Any],
    llm_client: Any,
    stream_output: bool = True,
) -> str:
    """Extract qualification/compliance review requirements from parsed sections."""
    messages = build_qualification_compliance_messages_from_sections(sections)
    return llm_client.think(messages, stream=stream_output) or ""


def extract_price_scoring_requirements(
    file_content: str,
    llm_client: Any,
    stream_output: bool = True,
) -> str:
    """Extract business and technical scoring requirements from raw text."""
    return llm_client.think(
        build_price_scoring_messages(file_content),
        stream=stream_output,
    ) or ""


def extract_price_scoring_requirements_from_sections(
    sections: Iterable[Any],
    llm_client: Any,
    stream_output: bool = True,
) -> str:
    """Extract business and technical scoring requirements from parsed sections."""
    messages = build_price_scoring_messages_from_sections(sections)
    return llm_client.think(messages, stream=stream_output) or ""


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
