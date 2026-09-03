# **算法2：规划与测试输入共演化的工作流合成闭环**

## **1. 问题定义**

给定：

* **用户需求（自然语言） **r
* 可检索知识库（工作流/节点规范、标准工作流示例、节点实现说明等） **\mathcal{K}**
* **当前工作流草案 **W^{(t)}**（JSON 形式，包含 **input_parameters**、节点集合 **nodes**、以及各节点 **input_map/choice_map/attrs** 等字段）**
* 形式化验证器（结构约束、字段约束、引用约束等） **\mathcal{V}**
* 工作流执行器/仿真器（可调用节点实现或 mock） **\mathcal{E}**

**目标是在有限迭代次数 **T** 内，联合生成：**

1. 可通过形式化验证的工作流 **W^\star**，并能处理代表性输入；
2. 与之匹配的系统级测试输入集合 **X^\star**，用于自动化回归测试与后续 bug 注入式迭代。

---

## **2. 核心思想：Plan 与 Test 同步生成、以执行反馈驱动修正**

传统“仅规划”会得到结构上合法但**不可执行**或**不可达**的工作流。算法2引入一个**测试输入合成器** **\mathcal{G}**，在每轮迭代中与规划模块并行/串行协作：

* **规划模块 **\mathcal{P}**：从需求 **r** 与已检索知识 **K^{(t)}** 生成候选工作流草案；**
* **测试输入合成器 **\mathcal{G}**：基于 **r**、**K^{(t)}**、当前工作流 **W^{(t)}**，生成****系统级测试输入**并对工作流做**输入映射适配**（**input_parameters** 与各节点 **input_map**）；
* 执行器 **\mathcal{E}**：用测试输入运行/仿真工作流，得到运行日志与错误；
* 修正器 **\mathcal{R}**：将错误归因到“可得性/可引用性/可执行性/路径覆盖不足”等类别，并形成对工作流的修正建议（作为下一轮补充输入）。

---

## **3. 可得性错误（Availability Error）的形式化定义**

为了让“执行失败 → 可学习的修正信号”更清晰，引入可得性错误集合 **\mathcal{A}**。典型包括：

1. **输入缺失**：工作流声明的系统级输入（**input_parameters**）与测试输入键集合不匹配；或节点期望字段在输入中缺失。
2. **引用不可达**：节点 input_map** 引用了不存在的源（如 **start.xxx**、**node_y.output_z** 不存在）。**
3. **类型/结构不匹配**：被引用字段存在但结构不符合节点实现期望（例如期望对象却给了字符串）。
4. **路径不可覆盖**：测试输入无法触发关键分支（**choice_map** 的判定条件无法满足），导致关键节点从未执行。
5. **终止/死循环异常**：无终止条件或分支指向错误导致无法结束。

在算法2中，**\mathcal{A}** 被视为**最优先**的修正对象：因为它们往往是“工作流在真实系统中不可用”的根因。

---

## **4. 工作流测试输入合成器 ** **\mathcal**** 的职责边界**

**合成器输入：**(r, K^{(t)}, W^{(t)})

输出：

* **workflow_draft_for_test**：对 **W^{(t)}** 做必要的**系统级输入映射补全**与**节点引用修正**（必要时增删改节点，但必须保持格式规范）
* **test_input**：系统级测试输入对象（建议包含“正常/边界/异常/缺失必填”等覆盖）
* **confidence**：合成器对适配正确性的置信度
* **reasoning_trace**：本轮设计依据（用于审计/迭代，不要求给最终用户）

这里把“测试输入”在理论上明确为一个集合：

* **单个测试输入样本：**x_i \in \mathcal{X}
* 最终输出建议为：**X^{(t)}=\{x_1,\dots,x_m\}**（工程里可以先实现为一个 dict，后续扩展成 list）

---

## **5. 算法2伪代码（Markdown / Algorithm 2）**

```
Algorithm 2: Planning–Testing Co-evolution for Workflow Synthesis

Input:
  requirement r
  knowledge base K (RAG index)
  validator V (schema + structural checks)
  executor E (workflow runner / simulator)
  max iterations T, retrieval budget B
Output:
  final workflow W*, test inputs X*, decision trace L

1:  Initialize t ← 0
2:  Initialize retrieved knowledge K^(0) ← Retrieve(K, query=r, budget=B0)
3:  Initialize workflow draft W^(0) ← P(r, K^(0))            // basic planning (Algorithm 1's plan)
4:  Initialize trace L ← ∅

5:  while t < T do
6:      // Step A: Test Input Synthesis + Input Adaptation
7:      (W_test^(t), X^(t), c_g, l_g) ← G(r, K^(t), W^(t))
8:      // W_test^(t) includes updated input_parameters and node input_map fixes

9:      // Step B: Formal Validation
10:     issues_v ← V(W_test^(t))
11:     if issues_v contains fatal errors then
12:         W^(t+1) ← Repair(W_test^(t), issues_v)           // structural repair (or ask model to patch)
13:         K^(t+1) ← OptionalRetrieve(K, issues_v, budget=B)
14:         Append(L, (t, "validate_fail", issues_v, l_g))
15:         t ← t + 1
16:         continue
17:     end if

18:     // Step C: Execution-based Testing
19:     (run_log, issues_e) ← E(W_test^(t), X^(t))

20:     // Step D: Availability-aware Diagnosis and Feedback
21:     issues_a ← FilterAvailabilityErrors(issues_e)
22:     if issues_a is empty and issues_e is empty then
23:         return (W_test^(t) as W*, X^(t) as X*, L)
24:     end if

25:     // Step E: Generate Workflow Fix Suggestions and Next Queries
26:     fix_hint ← R(r, W_test^(t), X^(t), issues_e, run_log)
27:     K^(t+1) ← Retrieve(K, query=fix_hint or issues_e, budget=B)
28:     W^(t+1) ← P(r ⊕ fix_hint, K^(t+1))                   // re-plan with augmented requirement
29:     Append(L, (t, "exec_fail", issues_e, issues_a, fix_hint, l_g))
30:     t ← t + 1
31:  end while

32:  return best-effort (W_test^(t), X^(t), L)
```

> 注：**\oplus** 表示将“修正意见/bug 信号”作为补充输入注入需求侧。

---

## **6. 关键设计点（写论文时建议强调的“理论贡献点”）**

### **6.1 规划与测试输入同步生成的必要性**

* 工作流是“节点编排程序”，仅靠结构合法无法保证可执行性；
* 测试输入合成将“隐含前提”显式化：让 **input_parameters** 与 **input_map** 在 JSON 层面对齐，减少“黑箱运行时崩溃”。

### **6.2 可得性错误优先修正的理由**

* 可得性错误通常是“系统级不可用”的硬阻断；
* 与业务逻辑错误相比，它们的修复更“局部”和“可形式化”，适合闭环自动修正与回归测试。

### **6.3 以执行日志作为可学习信号**

* 执行器 **\mathcal{E}** 输出的日志/报错天然就是“最强监督信号”；
* 形成 **fix_hint** 后再进入 RAG 与 re-plan，使得系统具备“自我纠错”的能力。


