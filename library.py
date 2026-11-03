"""青禾样例馆藏与读书计划工具，馆藏条目为自编演示资料。"""

BOOKS = [
    {"id":"B01","title":"Python 数据实践导读","author":"青禾编写组","topic":"编程","tags":"Python 数据分析 pandas","shelf":"三楼技术区 A-01","status":"样例在架","note":"从表格清洗入手，完成一次简单的数据分析。"},
    {"id":"B02","title":"开源 AI 项目入门","author":"青禾编写组","topic":"人工智能","tags":"AI 智能体 Agent 开源","shelf":"三楼技术区 A-02","status":"样例在架","note":"按工具调用、模型编排和演示验证三步理解智能体。"},
    {"id":"B03","title":"信息检索与来源评估","author":"青禾编写组","topic":"信息素养","tags":"检索 论文 参考文献 搜索","shelf":"二楼学习区 B-01","status":"样例在架","note":"学习扩展关键词、检查来源和记录引文。"},
    {"id":"B04","title":"机器学习实验笔记","author":"青禾编写组","topic":"人工智能","tags":"AI 机器学习 数据 模型","shelf":"三楼技术区 A-03","status":"样例借出","note":"通过小实验理解训练集、验证集和误差。"},
    {"id":"B05","title":"团队学习与项目复盘","author":"青禾编写组","topic":"学习方法","tags":"学习 小组 汇报 计划","shelf":"二楼学习区 B-02","status":"样例在架","note":"把小组任务拆成可验收的小步骤。"},
]


def catalog(query="", topic="全部"):
    words = query.casefold().split()
    return [b for b in BOOKS if (topic == "全部" or b["topic"] == topic)
            and all(w in " ".join(b.values()).casefold() for w in words)]


def study_plan(topic, minutes):
    topic = topic.strip()
    if not topic or len(topic) > 60 or type(minutes) is not int or not 15 <= minutes <= 240:
        raise ValueError("请输入 1–60 字的主题和 15–240 分钟的学习时间。")
    start, end = minutes // 5, minutes // 5
    return {"topic": topic, "minutes": minutes, "steps": [
        {"minutes": start, "task": "明确目标，写下两个待回答的问题。"},
        {"minutes": minutes - start - end, "task": "检索资料，阅读并记录结论及来源编号。"},
        {"minutes": end, "task": "用自己的话复述结论，列出下一步要验证的内容。"},
    ], "resources": catalog(topic)[:3]}
