"""青禾样例馆藏与读书计划工具，馆藏条目为自编演示资料。"""

import json
import re
from pathlib import Path

BOOKS = [
    {"id":"B01","title":"Python 数据实践导读","author":"青禾编写组","topic":"编程","tags":"Python 数据分析 pandas","shelf":"三楼技术区 A-01","status":"样例在架","note":"从表格清洗入手，完成一次简单的数据分析。"},
    {"id":"B02","title":"开源 AI 项目入门","author":"青禾编写组","topic":"人工智能","tags":"AI 智能体 Agent 开源","shelf":"三楼技术区 A-02","status":"样例在架","note":"按工具调用、模型编排和演示验证三步理解智能体。"},
    {"id":"B03","title":"信息检索与来源评估","author":"青禾编写组","topic":"信息素养","tags":"检索 论文 参考文献 搜索","shelf":"二楼学习区 B-01","status":"样例在架","note":"学习扩展关键词、检查来源和记录引文。"},
    {"id":"B04","title":"机器学习实验笔记","author":"青禾编写组","topic":"人工智能","tags":"AI 机器学习 数据 模型","shelf":"三楼技术区 A-03","status":"样例借出","note":"通过小实验理解训练集、验证集和误差。"},
    {"id":"B05","title":"团队学习与项目复盘","author":"青禾编写组","topic":"学习方法","tags":"学习 小组 汇报 计划","shelf":"二楼学习区 B-02","status":"样例在架","note":"把小组任务拆成可验收的小步骤。"},
] + json.loads(Path(__file__).with_name("catalog-extra.json").read_text(encoding="utf-8-sig"))

TOPICS = sorted({book["topic"] for book in BOOKS})


def catalog(query="", topic="全部"):
    words = query.casefold().split()
    return [b for b in BOOKS if (topic == "全部" or b["topic"] == topic)
            and all(w in " ".join(b.values()).casefold() for w in words)]


ACTIVITIES = {
    "exam": [("摸底", "闭卷写出已知知识和易错点", 2), ("练题", "限时完成代表题，逐题核对解法", 5), ("订正", "重做错题，写出错因和复习提醒", 3)],
    "project": [("拆需求", "写出交付物和验收条件", 2), ("做原型", "实现或画出一个最小可用成果", 6), ("验收", "对照验收条件检查，并记录未完成项", 2)],
    "reading": [("定问题", "写下这次阅读要回答的两个问题", 2), ("读与摘录", "定位关键章节，记录论点和出处", 5), ("复述", "合上资料，用自己的话写一段总结", 3)],
    "practice": [("选练习", "挑选一个能独立完成的小任务", 2), ("动手", "先独立尝试，遇到卡点再查资料", 6), ("复盘", "记录遇到的卡点，并设计一个变式练习", 2)],
}


def study_plan(topic, minutes, goal="reading", level="beginner", focus="", sessions=1):
    topic, focus = topic.strip(), focus.strip()
    if not topic or len(topic) > 60 or len(focus) > 200:
        raise ValueError("主题限 1–60 字，个人要求限 200 字。")
    if type(minutes) is not int or not 15 <= minutes <= 240:
        raise ValueError("请输入 15–240 分钟的可用时间。")
    if type(sessions) is not int or not 1 <= sessions <= 4 or minutes < 15 * sessions:
        raise ValueError("可安排 1–4 次学习，每次至少 15 分钟。")
    if goal not in ACTIVITIES or level not in ("beginner", "intermediate", "advanced"):
        raise ValueError("请选择有效的学习目标与基础。")
    subject = f"「{topic}」"
    if focus:
        subject += f"（重点：{focus}）"
    activities = list(ACTIVITIES[goal])
    label, task, weight = activities[0]
    if level == "beginner":
        activities[0] = (label, "先查一个入门例子，" + task, weight + 1)
    elif level == "advanced":
        activities[0] = (label, "先定位一个边界问题，" + task, weight)
    elif level == "intermediate":
        activities[0] = (label, "用已有知识解释一个典型例子，" + task, weight)
    steps = []
    total_weight = sum(item[2] for item in activities)
    for index in range(sessions):
        budget = minutes // sessions + (index < minutes % sessions)
        allocated = 0
        for position, (label, task, weight) in enumerate(activities):
            duration = budget * weight // total_weight if position < len(activities) - 1 else budget - allocated
            allocated += duration
            phase = "建立基线" if index == 0 else "用上次记录推进"
            steps.append({"session": index + 1, "minutes": duration,
                          "task": f"{label} · {phase}：围绕{subject}，{task}。"})
    resources = {}
    for term in [topic, *re.split(r"[\s、，,；;]+", focus)]:
        if term:
            for book in catalog(term):
                resources.setdefault(book["id"], book)
    return {"topic": topic, "minutes": minutes, "steps": steps, "resources": list(resources.values())[:5]}
