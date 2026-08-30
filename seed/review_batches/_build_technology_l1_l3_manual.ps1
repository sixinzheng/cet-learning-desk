$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$manifest = Get-Content (Join-Path $root 'seed\reading_source_manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$sample = (Get-Content (Join-Path $root 'seed\review_batches\technology_sample.json') -Raw -Encoding UTF8 | ConvertFrom-Json).passages
$items = [System.Collections.Generic.List[object]]::new()
$adaptation = '题材参考所列权威来源的公开事实；本站围绕独立中心问题重新组织信息并原创改写，非媒体原文，非历年真题。'

function Add-Passage($Number, $Level, $Title, $Verification, $Content, $Questions) {
    $sourceId = "src-科技-$('{0:D2}' -f $Number)"
    $meta = $sample | Where-Object source_id -eq $sourceId | Select-Object -First 1
    if (-not $meta) { $meta = $manifest | Where-Object source_id -eq $sourceId | Select-Object -First 1 }
    if (-not $meta) { throw "Missing source: $sourceId" }
    $balancedQuestions = [System.Collections.Generic.List[object]]::new()
    for ($questionIndex = 0; $questionIndex -lt $Questions.Count; $questionIndex++) {
        $question = $Questions[$questionIndex]
        $oldPosition = 'ABCD'.IndexOf([string]$question.answer)
        $correctText = [string]$question.options[$oldPosition]
        $distractors = [System.Collections.Generic.List[string]]::new()
        for ($optionIndex = 0; $optionIndex -lt 4; $optionIndex++) {
            if ($optionIndex -ne $oldPosition) { $distractors.Add([string]$question.options[$optionIndex]) }
        }
        $newPosition = ($Number + $Level + $questionIndex) % 4
        $newOptions = [System.Collections.Generic.List[string]]::new()
        $distractorIndex = 0
        for ($optionIndex = 0; $optionIndex -lt 4; $optionIndex++) {
            if ($optionIndex -eq $newPosition) { $newOptions.Add($correctText) }
            else { $newOptions.Add($distractors[$distractorIndex]); $distractorIndex++ }
        }
        $balancedQuestions.Add([ordered]@{
            type = $question.type
            question = $question.question
            options = $newOptions
            answer = 'ABCD'[$newPosition].ToString()
            explanation = $question.explanation
            evidence_text = $question.evidence_text
        })
    }
    $items.Add([ordered]@{
        corpus_id = "cet-manual-technology-l$Level-$('{0:D2}' -f $Number)"
        source_id = $sourceId
        title = $Title
        topic = '科技'
        difficulty = $Level
        source_name = $meta.source_name
        source_url = $meta.source_url
        source_title = $meta.source_title
        source_published_at = $meta.source_published_at
        retrieved_at = $meta.retrieved_at
        source_verification = $Verification
        adaptation_note = $adaptation
        content = $Content.Trim()
        questions = $balancedQuestions
    })
}

Add-Passage 1 1 'The Useful AI Test Happens on Tuesday Morning' '来源清单所列China Daily页面记录了AI行业由能力展示转向应用与可衡量产出的主线；样稿已核验同日有效正文，本文仅采用这一事实方向。' @'
An AI program may produce an exciting answer during a public show. A manager, however, meets a different question on an ordinary Tuesday: does the tool help people finish real work?

The answer depends on the setting. In a factory, useful software might notice a repeated fault before products leave the line. In an office, it might organize routine records so that staff can spend more time on difficult cases. A fast response is valuable only when workers can understand it and correct it when necessary.

This practical view changes the way success is measured. The size of a model or the amount of computing power does not directly tell a company how much time it saved. Teams should compare the old process with the new one. They should record errors, time, cost and the moments when a person had to step in.

Research still matters because better models make new uses possible. Yet research is a foundation, not the finished building. A system becomes valuable after it fits a task, earns users' trust and continues to work outside a prepared demonstration.

The strongest sign of progress may therefore look quite ordinary: a worker completes a useful job more safely or clearly than before.
'@ @(
    [ordered]@{type='main_idea';question='What practical test for AI guides the passage?';options=@('Whether it improves real work under normal conditions','Whether it surprises an audience during one show','Whether it uses more power than an older system','Whether it removes every worker from a process');answer='A';explanation='全文把AI评价标准从展示效果转向日常工作中的真实改进。';evidence_text='does the tool help people finish real work?'}
    [ordered]@{type='detail';question='Which results should teams record when comparing processes?';options=@('Only the model size and public reaction','Errors, time, cost and human intervention','The color of the software interface','The number of offices in the company');answer='B';explanation='第三段直接列出了错误、时间、成本和人工介入。';evidence_text='They should record errors, time, cost and the moments when a person had to step in.'}
    [ordered]@{type='word_guess';question='What does “foundation” suggest about AI research here?';options=@('It is the only part users ever see.','It is support on which useful applications are built.','It is a reason to avoid workplace testing.','It is a short public performance.');answer='B';explanation='下文把真正价值放在任务适配、信任和现场稳定性上，因此foundation指基础支撑。';evidence_text='Yet research is a foundation, not the finished building.'}
    [ordered]@{type='inference';question='Why is a fast answer not enough in the factory example?';options=@('Factory workers dislike all quick tools.','Every fault must remain hidden.','The output must also be understandable and correctable.','Office records are more important than products.');answer='C';explanation='速度只有在员工能理解并在必要时纠正结果时才有价值。';evidence_text='A fast response is valuable only when workers can understand it and correct it when necessary.'}
    [ordered]@{type='attitude';question='How does the writer regard technical advances in models?';options=@('As useful groundwork rather than final proof of value','As harmful to every established process','As more important than user trust','As unnecessary once one task works');answer='A';explanation='作者肯定研究会带来新用途，同时明确它不是完成态。';evidence_text='Research still matters because better models make new uses possible.'}
)

Add-Passage 6 1 'An Expo Ends When the Questions Begin' '来源清单记录China Daily关于重要博览会展示AI创新的页面；本文只采用“集中展示AI创新”这一可由标题确认的事实，不引入未列明数字。' @'
A technology expo can place many AI products in one hall. Visitors may watch a robot sort objects, hear software answer questions or see a machine create an image. Such demonstrations make new ideas easy to notice, but they do not settle whether a product is ready for daily use.

A short show usually controls the light, objects and instructions. Real users bring noisier conditions. They may speak in different ways, make unexpected requests or need help when the system fails. For this reason, a useful visitor asks what happened before the successful moment. How many trials were needed? What mistakes occurred? Who checked the result?

Expos still serve an important purpose. They allow engineers, buyers and researchers to compare approaches in a shared place. A hospital manager, for example, may discover a tool worth testing, while its maker learns which safety questions matter to medical staff. The meeting can begin cooperation.

The key word is begin. A promising exhibit should move next into a limited trial with real users and clear measures. If the trial reveals a weakness, that is information, not embarrassment. An expo shows what might be possible; careful follow-up shows what is dependable.
'@ @(
    [ordered]@{type='main_idea';question='What distinction does the author make about an AI expo?';options=@('It can introduce possibilities but cannot prove daily reliability.','It should admit engineers but exclude users.','It makes later testing unnecessary.','It is valuable only when no mistakes are discussed.');answer='A';explanation='文章反复区分展会中的可能性展示与真实场景中的可靠性验证。';evidence_text='An expo shows what might be possible; careful follow-up shows what is dependable.'}
    [ordered]@{type='detail';question='What can a hospital manager gain at the event?';options=@('A guarantee that every device is safe','A tool that may deserve a limited test','Permission to ignore medical staff','A complete replacement for hospital procedures');answer='B';explanation='第三段说医院管理者可能发现值得进一步测试的工具。';evidence_text='A hospital manager, for example, may discover a tool worth testing'}
    [ordered]@{type='word_guess';question='What does “controlled” mean in the description of a short show?';options=@('Held under arranged and predictable conditions','Open to every possible request','Repeated for many years','Managed only by a hospital');answer='A';explanation='后文用真实用户带来的嘈杂和意外情况作对比，说明controlled是条件被预先安排。';evidence_text='A short show usually controls the light, objects and instructions.'}
    [ordered]@{type='inference';question='Why does the passage call a failed trial informative?';options=@('It proves that innovation should stop.','It reveals a weakness that can be examined.','It makes safety questions unimportant.','It turns a buyer into an engineer.');answer='B';explanation='有限试验的价值包括暴露薄弱点，从而支持改进和判断。';evidence_text='If the trial reveals a weakness, that is information, not embarrassment.'}
    [ordered]@{type='purpose';question='Why are three visitor questions listed in paragraph 2?';options=@('To show how to look beyond a polished success','To teach visitors how to control lighting','To advertise one question-answering product','To discourage communication with makers');answer='A';explanation='三个问题都追问成功展示背后的试验、错误与核查，作用是引导审慎评价。';evidence_text='For this reason, a useful visitor asks what happened before the successful moment.'}
)

Add-Passage 7 1 'A Robot Tour Should Leave Students with a Method' '来源清单记录China Daily关于AI与机器人研学活动受欢迎的页面；本文仅采用研学活动增长这一事实方向。' @'
AI and robotics study tours have become popular with families. A child may enter a laboratory, guide a small robot or watch a machine respond to a voice command. The excitement is real, but a good tour should offer more than a collection of photographs.

The learning begins when students predict what a machine will do. After a trial, they can compare the result with their prediction. If the robot turns the wrong way, the guide should not quickly hide the failure. Students can check the sensor, the instruction and the surrounding space. In this way, an error becomes evidence.

Age also matters. Younger visitors may learn through a simple challenge with visible steps. Older students can discuss training data, privacy or why the same command produces different results. Giving every group the same technical lecture may sound efficient, but it can leave everyone confused.

Parents should receive clear information too. They need to know whether images or voices are recorded and how long any data is kept. A fun activity does not cancel the need for consent.

The best study tour does not try to prove that every child will become an engineer. It gives students a repeatable method: predict, test, observe and improve. That method can travel home even when the robot stays in the laboratory.
'@ @(
    [ordered]@{type='main_idea';question='What should students carry away from a robotics tour?';options=@('A repeatable way to investigate how a machine behaves','A promise that every visitor will become an engineer','A set of photographs without any questions','One lecture designed for every age group');answer='A';explanation='结尾把研学价值概括为可重复使用的探究方法。';evidence_text='It gives students a repeatable method: predict, test, observe and improve.'}
    [ordered]@{type='detail';question='What can learners inspect after a robot turns incorrectly?';options=@('Only the child who gave the command','The sensor, instruction and nearby space','The price of the laboratory building','The parents photographs');answer='B';explanation='第二段直接列出传感器、指令和周围空间三个检查对象。';evidence_text='Students can check the sensor, the instruction and the surrounding space.'}
    [ordered]@{type='word_guess';question='In paragraph 2, what does “evidence” mean?';options=@('Information that helps explain what happened','A prize for the fastest student','A picture used only for advertising','A rule that prevents another test');answer='A';explanation='错误被保留并用于检查原因，因此evidence指帮助解释现象的信息。';evidence_text='In this way, an error becomes evidence.'}
    [ordered]@{type='inference';question='Why should tour activities differ by age?';options=@('Older students are not allowed near robots.','Suitable tasks help each group understand rather than merely listen.','Young children can already discuss every privacy issue.','Technical lectures always work best for mixed groups.');answer='B';explanation='文章对比不同年龄的学习方式，并指出统一技术讲座会让所有人困惑。';evidence_text='Giving every group the same technical lecture may sound efficient, but it can leave everyone confused.'}
    [ordered]@{type='attitude';question='Which privacy responsibility applies during the fun robotics activity?';options=@('Recording is harmless whenever a robot is present.','Parents should be told about collection and retention.','Consent is needed only for older students.','All voices should be kept permanently.');answer='B';explanation='作者明确要求家长了解数据是否记录及保存多久，并强调同意仍然必要。';evidence_text='A fun activity does not cancel the need for consent.'}
)

Add-Passage 8 1 'A Robotics Boom Needs Repair Benches' '来源清单记录China Daily关于机器人创新进入活跃期的页面；本文只采用产业创新活跃这一事实方向。' @'
New robots often receive attention when they walk, dance or lift an object. A period of strong robotics innovation, however, also creates demand for less visible work. Machines need testing rooms, spare parts, software updates and people who can repair them.

This support system affects whether an invention becomes useful. A company may sell a capable robot to a factory far from its research team. If a sensor fails and no local technician can replace it, the machine may stand idle for weeks. The problem is not intelligence alone; it is service.

Training should therefore include maintenance workers as well as designers. Clear manuals can show which parts users may change safely. Digital records can help a technician see when a fault began. Standard connections may also make parts easier to obtain from more than one supplier.

These measures do not attract the same crowds as a lively demonstration. They matter after the cameras leave. Buyers should ask about repair time, update support and the future supply of parts before counting a robot as productive equipment.

An innovation boom is stronger when machines have a working life, not just a launch day. The quiet repair bench is part of the technology story because it keeps a promising device available for the people who depend on it.
'@ @(
    [ordered]@{type='main_idea';question='Which overlooked need during a robotics boom is emphasized?';options=@('Long-term maintenance and service for deployed machines','More dancing routines for public shows','Fewer records about equipment faults','A ban on standard connections');answer='A';explanation='全文说明维修、零件、更新和技术人员决定机器人能否长期发挥作用。';evidence_text='Machines need testing rooms, spare parts, software updates and people who can repair them.'}
    [ordered]@{type='detail';question='What may happen when no local technician can replace a failed sensor?';options=@('The robot becomes easier to sell.','The factory immediately designs a new sensor.','The machine may remain unused for weeks.','The research team no longer needs manuals.');answer='C';explanation='第二段直接说明缺少本地维修会导致机器闲置数周。';evidence_text='the machine may stand idle for weeks.'}
    [ordered]@{type='word_guess';question='What does “idle” mean in the factory situation?';options=@('Operating at maximum speed','Not being used or working','Connected to many suppliers','Ready for a public dance');answer='B';explanation='传感器无法更换导致机器人不能工作，idle在此意为闲置。';evidence_text='the machine may stand idle for weeks.'}
    [ordered]@{type='inference';question='Why can standard connections improve repair?';options=@('They make every robot perform the same task.','They may allow compatible parts from several sources.','They prevent technicians from reading records.','They remove the need for safety instructions.');answer='B';explanation='标准接口使替换件不必依赖单一来源，从而提高可维修性。';evidence_text='Standard connections may also make parts easier to obtain from more than one supplier.'}
    [ordered]@{type='attitude';question='What limitation of impressive launch events is highlighted?';options=@('They matter more than a machines useful life.','They are sufficient evidence for buyers.','They attract attention but leave important service questions unanswered.','They should replace repair training.');answer='C';explanation='作者承认展示吸引目光，但强调镜头离开后的维护保障更重要。';evidence_text='They matter after the cameras leave.'}
)

Add-Passage 9 1 'Growth Is Easy to Count; Readiness Is Not' '来源清单记录China Daily关于具身智能行业稳健增长的页面；本文仅采用行业增长这一事实方向。' @'
When an embodied-AI industry grows, reports can count companies, products or investment. Embodied AI refers to systems that learn and act through a physical machine, such as a robot. These totals describe activity, but they do not show whether a machine is ready to share space with people.

Readiness appears in smaller details. Can the robot stop when a child runs across its path? Does it recognize an object it has never held before? Can a worker understand why it refused a command? Answers require tests in varied settings, not one successful movement.

Growth also creates a need for common language. One company may call a task complete when a robot reaches the correct shelf. Another may require the machine to place an object safely and record the result. Without shared definitions, two success rates cannot be compared fairly.

This does not mean that industry numbers are useless. They can show where interest and resources are moving. They become more meaningful when paired with information about safety, repeated performance and the conditions of each test.

A young field should celebrate progress without confusing motion with maturity. The important question is not only how many machines exist, but how clearly their abilities and limits are understood.
'@ @(
    [ordered]@{type='word_guess';question='What does “embodied” indicate in embodied AI?';options=@('Acting through a physical machine','Existing only as written text','Working without any environment','Belonging to a financial report');answer='A';explanation='首段直接说明这类系统通过机器人等实体机器学习和行动。';evidence_text='Embodied AI refers to systems that learn and act through a physical machine, such as a robot.'}
    [ordered]@{type='main_idea';question='What warning accompanies the reported industry growth?';options=@('Product counts alone do not establish real-world readiness.','Physical machines cannot use artificial intelligence.','Common definitions always slow innovation.','Safety tests should use one fixed setting.');answer='A';explanation='全文强调增长指标必须与安全、重复表现和测试条件结合。';evidence_text='These totals describe activity, but they do not show whether a machine is ready to share space with people.'}
    [ordered]@{type='detail';question='Which unexpected event is proposed as a readiness test?';options=@('A company publishes an investment total.','A child suddenly crosses the robots path.','A robot reaches a familiar shelf.','Two firms use the same name.');answer='B';explanation='第二段用儿童突然进入路径检验机器人能否安全停止。';evidence_text='Can the robot stop when a child runs across its path?'}
    [ordered]@{type='inference';question='Why could two reported success rates be misleading?';options=@('The machines may have been judged by different definitions of completion.','Every company tests exactly the same action.','A higher rate always means a safer machine.','Success cannot be measured more than once.');answer='A';explanation='公司对任务完成的定义不同，数字便不具备公平可比性。';evidence_text='Without shared definitions, two success rates cannot be compared fairly.'}
    [ordered]@{type='attitude';question='What balance does the final paragraph recommend?';options=@('Ignore growth and discuss only failure.','Celebrate progress while examining abilities and limits.','Wait for complete maturity before any testing.','Replace clear definitions with larger totals.');answer='B';explanation='结尾既允许庆祝进步，也要求不把活跃误当成熟。';evidence_text='A young field should celebrate progress without confusing motion with maturity.'}
)

Add-Passage 2 2 'Useful Data Needs an Address' '来源清单页面已记录2025年中国产生52.26泽字节数据，以及AI推理数据超过训练数据等事实；样稿对该页面事实完成核验。' @'
China produced 52.26 zettabytes of data in 2025, more than one quarter above the previous year. The figure shows enormous digital activity. Yet production is only the first step in making information useful.

Organizations must decide where records belong. Some data supports an immediate service and can soon be removed. Other material may be needed for research, legal records or future training. Keeping everything together is not a neutral choice: storage consumes energy and money, while a crowded system can make an important file harder to locate.

Artificial intelligence adds a useful distinction. Training data helps a model learn patterns. Inference data is created when the trained model responds to requests. China's inference volume moved above its training volume in 2025, suggesting that more systems were being used after development. Still, frequent use says nothing by itself about whether the answers were accurate.

A sound data plan therefore begins with purpose. Owners should mark sensitive material, set a retention period and record who may use it. They also need tests for deletion, because a rule on paper is weak if copies remain in forgotten systems.

The challenge is not to build an endless digital warehouse. It is to give valuable information an address, a period of use and a responsible exit. Data becomes an asset only when people can find, protect and judge it.
'@ @(
    [ordered]@{type='detail';question='What national data total is reported for 2025?';options=@('52.26 zettabytes','25.52 gigabytes','One quarter of a zettabyte','2025 zettabytes');answer='A';explanation='首句直接给出2025年的数据产量。';evidence_text='China produced 52.26 zettabytes of data in 2025'}
    [ordered]@{type='word_guess';question='What does “retention” mean in the data plan?';options=@('The time for which information is kept','The speed of a model response','The price of a storage building','The number of public requests');answer='A';explanation='该词与保存期限和删除测试并列，指数据保留时长。';evidence_text='set a retention period and record who may use it.'}
    [ordered]@{type='inference';question='What does inference volume exceeding training volume suggest?';options=@('Training data has disappeared completely.','More trained systems are producing responses in use.','Every AI answer has become accurate.','Storage no longer consumes energy.');answer='B';explanation='推理数据来自模型响应请求，因此其增长说明部署使用增加，但不保证质量。';evidence_text='suggesting that more systems were being used after development.'}
    [ordered]@{type='main_idea';question='Which principle organizes the discussion of rapid data growth?';options=@('All records deserve permanent storage.','Large totals remove the need for management.','Information needs a defined purpose, protection and exit.','AI training is the only worthwhile data use.');answer='C';explanation='文章从增长转向分类、权限、保留和删除，中心是有目的的数据治理。';evidence_text='It is to give valuable information an address, a period of use and a responsible exit.'}
    [ordered]@{type='attitude';question='Which judgment is made about the 52.26-zettabyte total?';options=@('As proof that all stored information is valuable','As evidence of activity that still requires careful management','As a reason to stop AI development','As an exact measure of answer quality');answer='B';explanation='作者承认数字显示活动规模，但明确指出它只是让信息有用的第一步。';evidence_text='The figure shows enormous digital activity. Yet production is only the first step in making information useful.'}
)

Add-Passage 10 2 'A Smarter Robot Knows When to Pause' '来源清单记录China Daily关于机器人制造商把重点转向更高智能水平的页面；本文仅采用这一产业方向。' @'
Robot makers are shifting attention from movement alone toward greater intelligence. The phrase sounds like a simple upgrade, but intelligence in a physical machine is not just the ability to complete a longer list of commands.

A useful robot must connect perception with action. It may see a box, estimate whether the object is stable and choose how firmly to hold it. If part of the view is blocked, the machine should not behave as though nothing changed. It may slow down, look again or ask a worker for help.

That pause is sometimes treated as failure because it lowers the number of tasks completed per hour. In a shared workplace, however, uncertainty is information. A system that recognizes the edge of its knowledge can prevent a small doubt from becoming a damaged product or an injury.

Manufacturers therefore need more than successful examples in training data. They should include unusual objects, poor lighting and attempts that go wrong. Tests should record not only whether the final task was completed, but also how the robot responded when its first plan failed.

Greater intelligence does not mean hiding every decision inside a more complex model. Workers need clear signals about what the robot sees, why it stopped and what kind of help it requires. The smarter machine is not always the one that acts fastest. Sometimes it is the one that pauses for a good reason and makes that reason visible.
'@ @(
    [ordered]@{type='main_idea';question='Which behavior marks intelligence in the workplace robot described?';options=@('Acting quickly without reporting uncertainty','Managing uncertainty and communicating its limits','Following a longer fixed command list','Never asking a worker for assistance');answer='B';explanation='全文把更高智能解释为识别不确定性、调整行动并清楚沟通限制。';evidence_text='Sometimes it is the one that pauses for a good reason and makes that reason visible.'}
    [ordered]@{type='detail';question='What responses are suggested when a robots view is blocked?';options=@('Speed up and hold the object harder','End all work for the day','Slow down, observe again or request help','Pretend that the scene has not changed');answer='C';explanation='第二段直接给出减速、重新观察和求助三种反应。';evidence_text='It may slow down, look again or ask a worker for help.'}
    [ordered]@{type='word_guess';question='What does “edge” mean in “the edge of its knowledge”?';options=@('The physical side of a box','The limit beyond which the system is uncertain','A faster method of training','The boundary of a factory building');answer='B';explanation='语境讨论机器人识别自身不确定性，因此edge指知识能力的边界。';evidence_text='A system that recognizes the edge of its knowledge'}
    [ordered]@{type='inference';question='Why should failed attempts appear in training and tests?';options=@('They show whether the robot can recover safely from a broken plan.','They guarantee that poor lighting will disappear.','They allow manufacturers to hide completed tasks.','They make worker communication unnecessary.');answer='A';explanation='作者要求记录首次计划失败后的反应，用于判断恢复行为。';evidence_text='Tests should record not only whether the final task was completed, but also how the robot responded when its first plan failed.'}
    [ordered]@{type='attitude';question='How does the writer view a robot stopping because of doubt?';options=@('Always as a loss of intelligence','As potentially responsible behavior in a shared workplace','As evidence that sensors should be removed','As useful only in public demonstrations');answer='B';explanation='作者认为在共享工作场所，不确定性是一种信息，合理暂停可避免损害。';evidence_text='In a shared workplace, however, uncertainty is information.'}
)

Add-Passage 11 2 'A Leap Forward Needs a Longer Tape Measure' '来源清单记录China Daily回顾2025年具身智能行业显著进展的页面；本文只采用年度显著进展这一事实方向。' @'
A year of rapid progress in embodied intelligence may bring new robots, stronger components and more factory trials. Calling the change a leap forward captures its speed. It does not tell us which advances will remain useful after the year ends.

Different measures answer different questions. The number of prototypes shows how many ideas reached a physical form. Hours of operation reveal whether machines can continue working. Records of human intervention show where autonomy still breaks down. Repair time indicates whether a device can return to service without waiting for its original engineers.

These measures should follow the same robot over time. A machine may perform well during its first week because every part is new and operators are especially careful. After months of dust, updates and changing tasks, weaknesses that were invisible at launch can appear. Long-term records make this decline visible.

Comparison also needs context. A warehouse robot and a care robot face different risks, so one success score cannot describe both fairly. The first may be judged partly by speed and handling accuracy. The second must also protect privacy, use gentle contact and give people clear control.

Progress deserves recognition, but recognition should open a longer examination rather than close it. An industry has moved forward when its machines remain safe, repairable and useful as conditions change. The strongest annual story may be a system that keeps earning trust after its first impressive week.
'@ @(
    [ordered]@{type='main_idea';question='Why does rapid annual progress need a longer measurement period?';options=@('New robots should never be recognized.','Early success may not show lasting safety and usefulness.','Every machine becomes stronger with dust.','Annual reports must discuss only repair costs.');answer='B';explanation='文章主张用持续表现、维修和场景变化检验年度进展是否真实持久。';evidence_text='It does not tell us which advances will remain useful after the year ends.'}
    [ordered]@{type='detail';question='What does repair time reveal about a robot?';options=@('Whether it can return to work without its original engineering team','How many photographs were taken at launch','Whether it belongs in a care setting','How quickly a prototype receives a name');answer='A';explanation='第二段直接说明维修时间反映设备能否摆脱原研发团队而恢复服务。';evidence_text='Repair time indicates whether a device can return to service without waiting for its original engineers.'}
    [ordered]@{type='word_guess';question='What does “context” refer to in comparing robot scores?';options=@('The year printed on a report','The setting, tasks and risks surrounding the machine','The physical color of a component','The size of the original engineering team');answer='B';explanation='下文以仓库和照护场景的不同风险解释context。';evidence_text='A warehouse robot and a care robot face different risks, so one success score cannot describe both fairly.'}
    [ordered]@{type='inference';question='Why might weaknesses emerge only after several months?';options=@('Use introduces dust, updates and changing tasks absent from launch conditions.','Operators stop recording all results after one week.','Old machines are never repaired.','Care robots always move faster than warehouse robots.');answer='A';explanation='第三段说明长期运行条件会暴露首周看不到的问题。';evidence_text='After months of dust, updates and changing tasks, weaknesses that were invisible at launch can appear.'}
    [ordered]@{type='attitude';question='Why should annual recognition begin rather than end examination?';options=@('Praise should be followed by continued evaluation.','A successful year ends the need for evidence.','Only failed machines deserve long records.','Annual progress should be kept private.');answer='A';explanation='作者有条件地肯定进步，同时要求继续观察长期结果。';evidence_text='Progress deserves recognition, but recognition should open a longer examination rather than close it.'}
)

Add-Passage 12 2 'A Robotics Powerhouse Is Also a Network' '来源清单记录China Daily关于中国成为机器人产业重要力量的页面；本文仅采用产业能力扩展这一事实方向。' @'
A country may be called a robotics powerhouse because it designs many machines and supports large-scale manufacturing. Production matters, yet robots reach users through a wider network that includes component suppliers, software teams, testing sites, repair services and trained operators.

Weakness in one link can limit the whole system. A factory may receive a new robot but lack staff who understand its safety settings. A small developer may build useful software but be unable to test it on several kinds of hardware. A repair center may wait for a specialized part from a single supplier.

Common interfaces can reduce some of these problems. If components and software exchange information in agreed ways, companies can compare alternatives and replace parts more easily. Standards should not force every robot to look or act alike. Their job is to make important connections predictable while leaving room for better designs.

Skills are another part of capacity. Operators need to recognize unusual behavior, and technicians need access to accurate manuals and diagnostic tools. Training should continue after installation because software updates can change what a machine does.

The network also needs honest feedback. Users should be able to report recurring faults, and manufacturers should explain which machines may be affected. A large industry becomes dependable when information travels back from use to design.

Power, in this sense, is not only the ability to produce more robots. It is the ability to keep varied machines safe, useful and repairable across many real workplaces.
'@ @(
    [ordered]@{type='main_idea';question='What broader meaning of a robotics powerhouse is proposed?';options=@('A system able to support machines throughout real use','A nation that requires every robot to look alike','A factory that imports all specialized parts','A market measured only by production totals');answer='A';explanation='文章把产业力量扩展为供应、标准、技能、维修和反馈构成的全周期网络。';evidence_text='It is the ability to keep varied machines safe, useful and repairable across many real workplaces.'}
    [ordered]@{type='detail';question='What should happen after a robot is installed?';options=@('All training should immediately end.','Software should never receive an update.','Operator training should continue as behavior may change.','Safety settings should be hidden from staff.');answer='C';explanation='第四段明确指出安装后仍需培训，因为软件更新可能改变机器行为。';evidence_text='Training should continue after installation because software updates can change what a machine does.'}
    [ordered]@{type='word_guess';question='What does “interfaces” mean in paragraph 3?';options=@('Public faces used in advertisements','Shared ways for components and software to connect','Buildings where robots are displayed','Rules that make every design identical');answer='B';explanation='后句解释接口使部件和软件按约定方式交换信息。';evidence_text='If components and software exchange information in agreed ways'}
    [ordered]@{type='inference';question='How can user fault reports strengthen the network?';options=@('They allow problems found in use to improve design and warn others.','They prevent manufacturers from identifying affected machines.','They make diagnostic tools less accurate.','They replace the need for component suppliers.');answer='A';explanation='用户反馈可让现场信息返回设计端，并帮助说明受影响范围。';evidence_text='A large industry becomes dependable when information travels back from use to design.'}
    [ordered]@{type='purpose';question='Why are three weak-link examples given in paragraph 2?';options=@('To show that output scale can be limited by missing support','To argue that factories should avoid robots','To rank software above physical components','To prove that one supplier is always enough');answer='A';explanation='三个例子分别涉及操作、测试和零件，说明网络任一环节薄弱都会限制总体能力。';evidence_text='Weakness in one link can limit the whole system.'}
)

Add-Passage 13 2 'A Solar Wing Must Unfold into Evidence' '来源清单记录新华社英文网关于可卷展太阳翼体积可小至水瓶、用于空间场景的页面；本文仅采用紧凑卷收和在轨展开这一标题事实。' @'
A Chinese space company presented a rollable solar wing that can be packed into a space about the size of a water bottle. Compact storage solves an important launch problem: rockets offer limited room, while a satellite needs a much larger surface to collect sunlight after reaching orbit.

The idea depends on a reliable change of shape. During launch, the wing must remain tightly protected. In space, it has to unroll to the planned position without twisting or stopping halfway. Once open, it must keep producing power through temperature changes and repeated movement of the satellite.

Engineers therefore test more than whether the wing opens once. They may repeat folding and deployment, measure electrical output and examine how materials age. A test also needs realistic limits. A wing proven under one temperature range cannot automatically be trusted under every condition.

Compact design creates trade-offs. Thinner materials can save mass, but they may be easier to damage. A stronger support may improve stability while taking more launch space. The best design is not simply the smallest package; it balances volume, weight, power and reliability for a particular mission.

The water-bottle comparison helps the public imagine the folded size. Mission evidence must do the harder work. The solar wing succeeds only when a small object during launch becomes a dependable source of energy after deployment.
'@ @(
    [ordered]@{type='detail';question='What launch problem does the rolled form address?';options=@('Satellites receive too much sunlight.','Rockets have limited interior space.','Solar wings are too cold on Earth.','Electrical tests require large bottles.');answer='B';explanation='首段直接说明火箭空间有限，而太阳翼展开后需要更大面积。';evidence_text='rockets offer limited room, while a satellite needs a much larger surface to collect sunlight after reaching orbit.'}
    [ordered]@{type='main_idea';question='Which requirement matters beyond the wings compact size?';options=@('It must unfold and supply power reliably in mission conditions.','It should remain inside a bottle in orbit.','It must be the thinnest design available.','It should avoid repeated deployment tests.');answer='A';explanation='文章中心是紧凑卷收只有与可靠展开、发电和耐久结合才有意义。';evidence_text='The solar wing succeeds only when a small object during launch becomes a dependable source of energy after deployment.'}
    [ordered]@{type='word_guess';question='What does “trade-offs” mean in the design discussion?';options=@('Benefits in one area that may bring costs in another','Instructions for painting a satellite','Failures caused only by temperature','Measurements that never affect a mission');answer='A';explanation='下文以减重与易损、稳定与占空间的对立说明trade-offs指取舍。';evidence_text='Thinner materials can save mass, but they may be easier to damage.'}
    [ordered]@{type='inference';question='Why is one successful opening test insufficient?';options=@('The wing must also survive repetition and changing orbital conditions.','The folded package should become larger each time.','Satellites use solar wings only during launch.','Electrical output cannot be measured after deployment.');answer='A';explanation='真实任务还要求反复可靠、材料耐久和不同温度下的发电表现。';evidence_text='They may repeat folding and deployment, measure electrical output and examine how materials age.'}
    [ordered]@{type='attitude';question='Why is the water-bottle image included?';options=@('As complete proof that the wing is reliable','As a clear image of size, not a substitute for testing','As evidence that the wing stores drinking water','As a reason to ignore mission requirements');answer='B';explanation='结尾明确区分便于想象尺寸的比喻与真正证明可靠性的任务证据。';evidence_text='The water-bottle comparison helps the public imagine the folded size. Mission evidence must do the harder work.'}
)

Add-Passage 3 3 'A Robot Learns from the Almost-Dropped Box' '来源清单页面已记录机器人训练中心通过遥操作收集视觉、触觉与动作轨迹，以及现实动作数据稀缺等事实；样稿对该页面完成核验。' @'
For a person, lifting a box is one action. For a humanoid robot, it is a sequence of judgments about distance, grip, balance and movement. This explains why a robot training center may repeat an ordinary task thousands of times.

A human trainer can guide a machine while sensors record images, pressure, joint force and motion. The resulting trajectory shows how the robot moved from its first observation to the final position. Collections of such paths help a learning system connect what it senses with what it should do next.

Physical data is harder to gather than online text. There is no enormous public library showing many robot hands touching unfamiliar objects under every kind of light. Each new trial needs equipment, space and time. Touch is especially difficult because machines use different sensors, making records harder to combine.

Repetition alone does not solve the problem. If trainers keep only smooth, successful lifts, a model may learn little about danger. The almost-dropped box can be more valuable because it shows slipping, correction and a safe decision to stop. A useful dataset includes variation as well as recovery from error.

This choice affects later deployment. A robot trained only with perfect boxes may fail when packaging is bent, wet or partly hidden. Trainers are therefore not merely collecting more examples; they are deciding which parts of the physical world the machine will be prepared to recognize.

The quality of robot learning depends on the ordinary difficulties preserved in its experience. Removing every messy attempt may create clean data, but it can also produce a machine that is surprised by normal life.
'@ @(
    [ordered]@{type='main_idea';question='Why can an almost-dropped box improve robot training?';options=@('It records error and recovery that clean success may omit.','It removes the need for physical sensors.','It proves that online text teaches every movement.','It allows trainers to avoid repeated trials.');answer='A';explanation='文章用险些掉落的箱子说明错误轨迹能教会机器人识别打滑、纠正和安全停止。';evidence_text='The almost-dropped box can be more valuable because it shows slipping, correction and a safe decision to stop.'}
    [ordered]@{type='detail';question='Which signals are captured while the trainer guides the machine?';options=@('Images, pressure, joint force and motion','Only the final shelf number','Public text and private messages','Weather reports from many cities');answer='A';explanation='第二段直接列出图像、压力、关节力和运动信号。';evidence_text='sensors record images, pressure, joint force and motion.'}
    [ordered]@{type='inference';question='Why are touch records difficult to combine across robots?';options=@('Different machines may measure touch with unlike sensors.','Touch can be copied from any online book.','Every robot uses one international hand.','Pressure never changes during a lift.');answer='A';explanation='各机器传感器不同，数据表示便难以直接合并。';evidence_text='Touch is especially difficult because machines use different sensors, making records harder to combine.'}
    [ordered]@{type='word_guess';question='What does “trajectory” describe in this passage?';options=@('A list of robot prices','The recorded path from sensing to final movement','A room used to store boxes','A rule for deleting failed trials');answer='B';explanation='正文随后解释它记录从最初观察到最终位置的运动过程。';evidence_text='The resulting trajectory shows how the robot moved from its first observation to the final position.'}
    [ordered]@{type='attitude';question='What is the writers view of perfectly clean training data?';options=@('It is always the safest possible choice.','It is useful only for learning from text.','It may hide normal difficulties the robot must handle.','It makes variation unnecessary.');answer='C';explanation='作者警告删除混乱尝试会让机器人对正常现实情况缺乏准备。';evidence_text='Removing every messy attempt may create clean data, but it can also produce a machine that is surprised by normal life.'}
)

Add-Passage 14 3 'An Industrial Park Cannot Manufacture Cooperation' '来源清单记录新华社英文网关于北京启动卫星互联网产业园和重点实验室的页面；本文仅采用产业园与实验室共同设立这一事实。' @'
Beijing launched an industrial park and key laboratories for satellite internet. Placing companies and researchers near one another can shorten travel, make equipment easier to share and create more chances for technical discussion. Yet a common address does not automatically produce a common system.

Satellite internet joins spacecraft, launch services, ground stations, user terminals and network software. Each part may be developed by a different organization. A change in one interface can force several partners to redesign their work. Teams therefore need shared technical descriptions, testing schedules and a clear way to report changes.

Laboratories and companies also follow different clocks. Researchers may explore a risky idea whose value is uncertain, while a manufacturer needs a stable design for delivery. Cooperation works when these roles are visible. A test platform can protect experimental freedom without allowing an unfinished component to enter an operational network unnoticed.

Physical closeness may even hide weak communication. People can attend the same meeting yet use different definitions for reliability, delay or successful connection. Joint tests reveal such gaps because every team must explain what it expected and what actually occurred.

The park should also leave doors open to outside expertise. Universities, smaller suppliers and users in remote places may identify problems that the main members overlook. Access rules must protect sensitive designs without turning shared facilities into a private club.

An industrial cluster is therefore an opportunity for coordination, not proof of it. Its achievement should be measured by compatible systems, faster problem-solving and knowledge that crosses organizational boundaries with clear responsibility.
'@ @(
    [ordered]@{type='main_idea';question='What must a satellite-internet cluster achieve beyond physical closeness?';options=@('Visible coordination across technical and organizational boundaries','One building for every user terminal','Identical research and manufacturing schedules','Complete secrecy from outside specialists');answer='A';explanation='全文说明共址只有转化为接口、测试、责任和知识协作才有价值。';evidence_text='An industrial cluster is therefore an opportunity for coordination, not proof of it.'}
    [ordered]@{type='detail';question='Which parts of satellite internet are named as connected?';options=@('Aircraft cabins, roads and ocean ports','Spacecraft, launch services, ground stations, terminals and software','Only laboratories and meeting rooms','Factories, hospitals and farm machines');answer='B';explanation='第二段直接列出卫星互联网的多个组成部分。';evidence_text='Satellite internet joins spacecraft, launch services, ground stations, user terminals and network software.'}
    [ordered]@{type='word_guess';question='What do different “clocks” represent for labs and companies?';options=@('Separate time zones in Beijing','Different working horizons and needs for certainty','A failure to attend the same meeting','The speed of a satellite signal');answer='B';explanation='后文对比科研探索不确定想法与制造商需要稳定交付设计，clocks比喻不同节奏。';evidence_text='Researchers may explore a risky idea whose value is uncertain, while a manufacturer needs a stable design for delivery.'}
    [ordered]@{type='inference';question='Why can joint tests expose communication gaps?';options=@('They require teams to compare expected and actual behavior.','They prevent any interface from changing.','They make all technical terms unnecessary.','They replace operational networks with meetings.');answer='A';explanation='联合测试迫使各团队说明预期和实际结果，因而能发现术语和接口理解差异。';evidence_text='Joint tests reveal such gaps because every team must explain what it expected and what actually occurred.'}
    [ordered]@{type='purpose';question='What role do universities and remote users play in the argument?';options=@('They show why valuable criticism should also enter from outside the cluster','They prove that sensitive designs should be public','They limit the park to large manufacturers','They show that remote places need no terminals');answer='A';explanation='这些外部参与者可能发现核心成员忽略的问题，用于说明开放边界的重要性。';evidence_text='Universities, smaller suppliers and users in remote places may identify problems that the main members overlook.'}
)

Add-Passage 15 3 'Commercial Space Cooperation Needs Shared Verbs' '来源清单记录新华社英文网关于航天机构推动商业增长与国际合作计划的页面；本文仅采用增长和国际合作并列这一事实方向。' @'
A space agency can encourage commercial growth and international cooperation in the same plan. The two goals may support each other: companies can provide specialized services, while partners across borders contribute knowledge, markets and observation sites. The difficulty begins when broad promises meet operational details.

Partners first need shared verbs. “Test” may mean a laboratory check to one team and a flight demonstration to another. “Deliver” may describe arrival at a launch site or a service that has worked for several months. Contracts and technical plans should define these actions, the evidence required and the person responsible for accepting a result.

Commercial schedules can move faster than government agreements. Speed may encourage experimentation, but it can also leave questions about export rules, spectrum use, safety review or data access until late in a project. Early legal and technical review is not simply delay; it can prevent a completed component from becoming unusable.

International cooperation also needs a plan for failure. If a launch is postponed or an instrument stops working, teams must know who communicates with users, who investigates and which data can be shared. A fair agreement distributes both opportunity and repair duties.

Growth should not be measured only by the number of signed projects. A smaller partnership that produces compatible equipment, trustworthy data and repeated service may create more value than a long list of uncertain intentions. Public reports can help by separating agreements, tests, launches and operating services.

The plan succeeds when different actors can do more than announce the same goal. They must use shared meanings, meet visible responsibilities and learn together when space refuses to follow the schedule.
'@ @(
    [ordered]@{type='main_idea';question='What turns commercial and international space plans into workable cooperation?';options=@('Shared definitions, evidence and responsibility','A longer list of unsigned intentions','One schedule that never changes','Avoiding discussion of failure');answer='A';explanation='全文从术语、证据、法规和故障责任说明合作需要可操作的共同规则。';evidence_text='They must use shared meanings, meet visible responsibilities and learn together when space refuses to follow the schedule.'}
    [ordered]@{type='word_guess';question='What are the “shared verbs” in paragraph 2?';options=@('Foreign-language words used by astronauts','Clearly defined actions such as testing and delivery','Commands for moving a satellite by hand','Names of commercial companies');answer='B';explanation='段落用test和deliver说明合作方必须对关键行动含义达成一致。';evidence_text='Contracts and technical plans should define these actions, the evidence required and the person responsible for accepting a result.'}
    [ordered]@{type='detail';question='Which possible obstacles should receive early review?';options=@('Export rules, spectrum, safety and data access','Office furniture and public photographs','Only the final project title','The number of verbs in a contract');answer='A';explanation='第三段直接列出出口规则、频谱、安全审查和数据访问。';evidence_text='questions about export rules, spectrum use, safety review or data access'}
    [ordered]@{type='inference';question='Why can a smaller partnership create greater value?';options=@('It may deliver compatible equipment and reliable service instead of uncertain promises.','Small projects never experience launch delays.','International partners do not need contracts.','Signed project totals always measure operating quality.');answer='A';explanation='作者对比可持续交付成果的小型合作与只有意向数量的长清单。';evidence_text='A smaller partnership that produces compatible equipment, trustworthy data and repeated service may create more value than a long list of uncertain intentions.'}
    [ordered]@{type='attitude';question='Which role does early legal and technical review play here?';options=@('A needless obstacle to all experimentation','Useful prevention against later unusable work','A task that belongs only after launch','Proof that commercial schedules must stop');answer='B';explanation='作者认为早期审查不是单纯拖延，而能避免完成的部件因规则问题无法使用。';evidence_text='Early legal and technical review is not simply delay; it can prevent a completed component from becoming unusable.'}
)

Add-Passage 16 3 'A Top-Ten List Is a Doorway, Not a Map' '来源清单记录China Daily发布中国2024年度十大科技成果的页面；本文仅采用“年度十大成果清单”这一事实。' @'
A list of ten major science and technology achievements can help a wide audience notice work that would otherwise remain inside laboratories. The short format is memorable. It also creates a risk: readers may treat unlike achievements as if they had won the same race.

Scientific results mature in different ways. One may explain a basic process without an immediate product. Another may improve a machine already used in industry. A third may be a demonstration that still requires years of testing. Placing them together communicates importance, not identical readiness.

Selection also reflects a purpose. A list designed for researchers might emphasize new knowledge, while one for the public may favor results that can be explained clearly. Neither choice is automatically wrong, but the criteria should be visible. Otherwise, omission may be mistaken for failure and inclusion for a promise of quick use.

Good science communication can use the list as a doorway. Each item should lead readers to questions about evidence, uncertainty, contributors and next steps. Follow-up reports can explain whether a result was repeated, whether other teams examined it and what barriers remain before wider application.

The order deserves care as well. A numbered presentation is easy to read, yet it may suggest a ranking even when no direct comparison was made. Categories or short explanations can reduce that false message.

Annual recognition is valuable because attention can support learning and future work. Its purpose is not to close discussion with ten winners. It should open ten clearer conversations about how knowledge develops and how society can judge progress without demanding that every discovery become a product tomorrow.
'@ @(
    [ordered]@{type='main_idea';question='How should readers use an annual top-ten science list?';options=@('As a starting point for deeper questions about different achievements','As proof that all ten results are equally ready for market','As a final ranking that ends scientific discussion','As evidence that omitted work has failed');answer='A';explanation='文章主张把清单当作深入了解证据、成熟度和下一步的入口。';evidence_text='Good science communication can use the list as a doorway.'}
    [ordered]@{type='detail';question='What differences among achievements does paragraph 2 identify?';options=@('They may be basic knowledge, an industrial improvement or an early demonstration.','They must all be finished consumer products.','They use identical evidence and schedules.','They are selected only by product price.');answer='A';explanation='第二段列出基础解释、产业改进和仍需测试的示范三种不同成熟路径。';evidence_text='One may explain a basic process without an immediate product. Another may improve a machine already used in industry. A third may be a demonstration that still requires years of testing.'}
    [ordered]@{type='word_guess';question='What does “criteria” mean in the selection discussion?';options=@('Standards used to decide what enters the list','Dates on which products are sold','Names of all laboratory workers','Reasons to avoid public explanation');answer='A';explanation='criteria指清单选择所依据的标准，作者要求这些标准公开。';evidence_text='the criteria should be visible.'}
    [ordered]@{type='inference';question='Why might categories be better than simple numbering?';options=@('They can avoid implying an unsupported direct ranking.','They guarantee every discovery becomes a product.','They remove the need to explain evidence.','They make the list harder to remember.');answer='A';explanation='编号容易被理解为名次，而类别和说明可减少这种错误信息。';evidence_text='A numbered presentation is easy to read, yet it may suggest a ranking even when no direct comparison was made.'}
    [ordered]@{type='purpose';question='Why does the passage contrast lists for researchers and the public?';options=@('To show that selection depends on audience and declared purpose','To prove that public readers dislike clear explanations','To require two identical lists every year','To argue that researchers need no communication');answer='A';explanation='对比说明不同受众会影响选取重点，因此必须公开目的与标准。';evidence_text='A list designed for researchers might emphasize new knowledge, while one for the public may favor results that can be explained clearly.'}
)

Add-Passage 17 3 'Commercial Space Begins After the Launch Applause' '来源清单记录新华社英文网关于中国商业航天加速并拓展到发射之外的页面；本文仅采用产业链向发射后服务扩展这一事实方向。' @'
A rocket launch is easy to recognize as a commercial-space event. Fire, sound and a rising vehicle create a clear moment of success. Yet an industry that expands beyond launches must also perform quieter work before and after that moment.

Satellite makers need reliable components and tests before departure. Once a spacecraft reaches orbit, ground stations must receive data, software teams must operate the service and customers need terminals or useful information. Insurance, maintenance planning and end-of-life disposal connect the mission to responsibilities that may last for years.

This longer chain changes the meaning of delay. A late launch does not affect only the launch company. It may leave a satellite producer waiting, keep a data service from earning income and force users to continue with an older system. Transparent schedules and compatible interfaces can help partners find alternatives.

Business growth also depends on repeat customers. A dramatic first mission can attract attention, but organizations pay again when a service is available, accurate and supported. Contracts should therefore distinguish a successful launch from the later delivery of communication, images or other promised results.

Failure must produce knowledge rather than only blame. Companies have legitimate secrets, but shared safety findings can prevent another operator from repeating a dangerous mistake. Clear investigation rules can protect necessary information while still warning the wider sector.

Commercial space reaches maturity when value can be traced across the whole service. Launches remain essential, but they are one link between design, operation, customer use and responsible disposal. The applause marks a beginning; dependable work over time completes the business case.
'@ @(
    [ordered]@{type='main_idea';question='What does moving “beyond launches” require from commercial space?';options=@('A dependable service chain before and after flight','More public applause for every rocket','Contracts that end when a vehicle rises','Less attention to customer results');answer='A';explanation='全文把商业航天扩展为制造、地面运营、用户服务、调查和处置构成的链条。';evidence_text='Commercial space reaches maturity when value can be traced across the whole service.'}
    [ordered]@{type='detail';question='Which activities continue after a satellite enters orbit?';options=@('Ground reception, software operation and customer service','Rocket painting and launch rehearsal only','Factory construction inside the satellite','Removal of every user terminal');answer='A';explanation='第二段直接描述入轨后的地面站接收、软件运营及客户使用。';evidence_text='Once a spacecraft reaches orbit, ground stations must receive data, software teams must operate the service and customers need terminals or useful information.'}
    [ordered]@{type='word_guess';question='What does “compatible” mean for partner interfaces?';options=@('Able to work together or allow substitution','Kept secret from every partner','Used only during public launches','Designed to create longer delays');answer='A';explanation='语境说透明日程和兼容接口帮助伙伴寻找替代路线，因此compatible指能够协同。';evidence_text='Transparent schedules and compatible interfaces can help partners find alternatives.'}
    [ordered]@{type='inference';question='Why can one delayed launch harm several businesses?';options=@('Several services and producers depend on the same flight schedule.','Every satellite is built by the launch company.','Users always prefer an older system.','Insurance forbids schedule changes.');answer='A';explanation='第三段列出卫星制造商、数据服务和用户都会受到同一延误影响。';evidence_text='It may leave a satellite producer waiting, keep a data service from earning income and force users to continue with an older system.'}
    [ordered]@{type='attitude';question='What position does the writer take on sharing failure information?';options=@('All commercial secrets should be published.','Safety lessons should be shared under clear protective rules.','Only blame should be announced publicly.','Other operators cannot learn from an accident.');answer='B';explanation='作者兼顾商业秘密与公共安全，主张在调查规则下共享必要安全发现。';evidence_text='Clear investigation rules can protect necessary information while still warning the wider sector.'}
)

$output = [ordered]@{
    batch_id = 'technology-l1-l3-manual-2026-08-29'
    status = 'review_only'
    runtime_imported = $false
    passages = $items
}
$target = Join-Path $root 'seed\review_batches\technology_l1_l3_manual.json'
$output | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $target -Encoding UTF8
Write-Host "Wrote $($items.Count) passages to $target"
