# -*- coding: utf-8 -*-
"""CLI界面渲染 —— 使用rich库"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from models.state import WorldState, TickResult


console = Console()


class CLIRenderer:

    def render_intro(self, world: WorldState):
        """渲染游戏开场"""
        console.clear()
        intro = Text()
        intro.append("异 星 求 生\n", style="bold cyan")
        intro.append(f"场景：{world.scenario_name}\n\n", style="dim")

        loc = world.locations[world.player.location]
        intro.append("你睁开眼睛。\n\n", style="italic")
        intro.append(loc.description + "\n\n")
        intro.append("输入 help 或 帮助 查看可用指令。\n", style="dim")

        console.print(Panel(intro, border_style="cyan", box=box.DOUBLE))

    def render_world(self, world: WorldState):
        """渲染当前世界状态——不显示精确时间，只给环境描述"""
        status = world.player.status

        # 标题行：天数 + 环境描述 + 天气
        day = world.current_day
        time_desc = world.time_description
        weather = world.weather

        console.print(f"\n{'─' * 50}", style="dim")
        tech_num, tech_name = world.tech_level
        console.print(f"第{day}天 | {weather} | 科技：{tech_name}", style="bold")
        console.print(f"{time_desc}", style="italic dim")
        console.print(f"{'─' * 50}", style="dim")

        # 状态栏
        status_table = Table(show_header=False, box=None, padding=(0, 2))
        status_table.add_column(style="white")
        status_table.add_column(style="white")
        status_table.add_column(style="white")
        status_table.add_column(style="white")
        status_table.add_column(style="white")

        hp_style = "green" if status.health > 5 else ("yellow" if status.health > 2 else "red bold")
        hunger_style = "green" if status.hunger < 5 else ("yellow" if status.hunger < 8 else "red bold")
        thirst_style = "green" if status.thirst < 5 else ("yellow" if status.thirst < 8 else "red bold")
        warmth_style = "green" if status.warmth > 4 else ("yellow" if status.warmth > 2 else "red bold")
        energy_style = "green" if status.energy > 3 else ("yellow" if status.energy > 1 else "red bold")

        status_table.add_row(
            Text(f"生命 {status.health}/{status.max_health}", style=hp_style),
            Text(f"饥饿 {status.hunger}/{status.max_hunger}", style=hunger_style),
            Text(f"口渴 {status.thirst}/{status.max_thirst}", style=thirst_style),
            Text(f"体温 {status.warmth}/{status.max_warmth}", style=warmth_style),
            Text(f"体力 {status.energy}/{status.max_energy}", style=energy_style),
        )
        console.print(status_table)

    def render_result(self, tick_result: TickResult):
        """渲染动作结果"""
        result = tick_result.action_result

        # 添加 [系统] 标记，方便查看log时区分系统输出
        msg = f"[系统] {result.message}"
        if result.success:
            console.print(f"\n{msg}", style="white")
        else:
            console.print(f"\n{msg}", style="yellow")

        # 事件
        for event in tick_result.events:
            console.print(f"  >> {event}", style="magenta")

        # 状态变化
        if tick_result.status_before and tick_result.status_after:
            changes = []
            for key in ['health', 'hunger', 'thirst', 'warmth', 'energy']:
                before = tick_result.status_before.get(key, 0)
                after = tick_result.status_after.get(key, 0)
                diff = after - before
                if diff != 0:
                    label = {'health': '生命', 'hunger': '饥饿', 'thirst': '口渴',
                             'warmth': '体温', 'energy': '体力'}[key]
                    sign = '+' if diff > 0 else ''
                    if key in ('hunger', 'thirst'):
                        style = "red" if diff > 0 else "green"
                    else:
                        style = "green" if diff > 0 else "red"
                    changes.append(Text(f"{label}{sign}{diff}", style=style))

            if changes:
                line = Text("  状态变化：")
                for i, c in enumerate(changes):
                    if i > 0:
                        line.append("  ")
                    line.append_text(c)
                console.print(line)

    def render_game_over(self, world: WorldState, scores: dict):
        """渲染游戏结束画面"""
        console.print(f"\n{'═' * 50}", style="bold")

        if any(g.completed and g.id == 'signal' for g in world.goals):
            console.print("任 务 完 成", style="bold green", justify="center")
        else:
            console.print("游 戏 结 束", style="bold red", justify="center")

        console.print(f"{world.game_over_reason}\n", style="italic")

        # 得分表
        score_table = Table(title="评估报告", box=box.SIMPLE)
        score_table.add_column("指标", style="cyan")
        score_table.add_column("数值", justify="right")

        score_table.add_row("存活天数", str(scores['days_survived']))
        score_table.add_row("累计小时", str(scores['hours_survived']))
        score_table.add_row("执行动作", str(scores['actions_taken']))
        score_table.add_row("目标完成", f"{scores['goals_completed']}/{scores['goals_total']}")
        score_table.add_row("有效动作率", f"{(1 - scores['invalid_rate']) * 100:.0f}%")
        score_table.add_row("探索覆盖", scores['exploration'])
        score_table.add_row("工具发明", str(scores['inventions']))
        score_table.add_row("科技等级", f"{scores['tech_level']}（{scores['tech_points']}点）")
        score_table.add_row("最终生命", str(scores['final_health']))

        console.print(score_table)

        # LLM调用计费
        cost = scores.get('cost')
        if cost and cost['total_calls'] > 0:
            cost_table = Table(title="LLM计费汇总", box=box.SIMPLE)
            cost_table.add_column("模型", style="cyan")
            cost_table.add_column("调用次数", justify="right")
            cost_table.add_column("输入token", justify="right")
            cost_table.add_column("输出token", justify="right")
            cost_table.add_column("费用(¥)", justify="right", style="yellow")

            for model, info in cost.get('by_model', {}).items():
                cost_table.add_row(
                    model,
                    str(info['calls']),
                    str(info['input_tokens']),
                    str(info['output_tokens']),
                    f"¥{info['cost_cny']:.4f}",
                )
            cost_table.add_row(
                "合计", str(cost['total_calls']),
                str(cost['total_input_tokens']),
                str(cost['total_output_tokens']),
                f"¥{cost['total_cost_cny']:.4f}",
                style="bold",
            )
            console.print(cost_table)

        console.print(f"{'═' * 50}\n", style="bold")

    def get_input(self) -> str:
        """获取玩家输入"""
        try:
            return console.input("\n[bold cyan]> [/]").strip()
        except (EOFError, KeyboardInterrupt):
            return 'quit'

    def render_checkpoint(self, world: WorldState, scores: dict) -> bool:
        """渲染检查点报告，返回是否继续"""
        console.print(f"\n{'═' * 50}", style="bold yellow")
        console.print(f"阶段检查点 —— 第{world.checkpoints_passed + 1}阶段（第{world.current_day}天）", style="bold yellow", justify="center")
        console.print(f"{'═' * 50}", style="bold yellow")

        # 简要报告
        tech_num, tech_name = world.tech_level
        console.print(f"  存活天数：{scores['days_survived']}  |  科技：{tech_name}（{scores['tech_points']}点）  |  发明：{scores['inventions']}", style="white")
        console.print(f"  有效动作率：{(1 - scores['invalid_rate']) * 100:.0f}%  |  探索：{scores['exploration']}", style="white")

        # 费用
        cost = scores.get('cost')
        if cost and cost['total_calls'] > 0:
            console.print(f"  LLM调用：{cost['total_calls']}次  |  累计费用：¥{cost['total_cost_cny']:.4f}", style="yellow")

        console.print(f"\n继续下一阶段？（输入 y 继续，其他退出）", style="bold cyan")
        answer = self.get_input()
        return answer.lower() in ('y', 'yes', '是', '继续')

    def render_message(self, msg: str, style: str = "white"):
        console.print(msg, style=style)
