$ErrorActionPreference='Stop'
$root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$manifest=Get-Content (Join-Path $root 'seed\reading_source_manifest.json') -Raw -Encoding UTF8|ConvertFrom-Json
$sample=(Get-Content (Join-Path $root 'seed\review_batches\technology_sample.json') -Raw -Encoding UTF8|ConvertFrom-Json).passages
$items=[System.Collections.Generic.List[object]]::new()
$adapt='题材参考所列权威来源的公开事实；本站围绕独立中心问题重组结构并原创改写，非媒体原文，非历年真题。'
function Add-Tech($Number,$Level,$Title,$Content,$Verification,$Qs){
 $sid="src-科技-$('{0:D2}' -f $Number)";$meta=$manifest|? source_id -eq $sid|Select -First 1
 if(-not $meta){$meta=$sample|? source_id -eq $sid|Select -First 1}
 $ql=[System.Collections.Generic.List[object]]::new();$wrong=@('The case proves that scale alone guarantees reliable results.','Human review becomes unnecessary once new equipment appears.','One successful trial settles every question about later use.','The reported technology removes all cost and safety trade-offs.','A headline number is sufficient without context or comparison.','The system can be judged without observing its actual users.')
 for($i=0;$i -lt 5;$i++){ $q=$Qs[$i];$pos=($Number+$i)%4;$opts=[System.Collections.Generic.List[string]]::new();$k=0;for($j=0;$j-lt4;$j++){if($j-eq$pos){$opts.Add($q[2])}else{$opts.Add($wrong[($Number+$i+$k)%$wrong.Count]);$k++}};$ql.Add([ordered]@{type=$q[0];question=$q[1];options=$opts;answer='ABCD'[$pos].ToString();explanation=$q[4];evidence_text=$q[3]}) }
 $items.Add([ordered]@{corpus_id="cet-manual-technology-l$Level-$('{0:D2}' -f $Number)";source_id=$sid;title=$Title;topic='科技';difficulty=$Level;source_name=$meta.source_name;source_url=$meta.source_url;source_title=$meta.source_title;source_published_at=$meta.source_published_at;retrieved_at='2026-08-29';source_verification=$Verification;adaptation_note=$adapt;content=$Content.Trim();questions=$ql})
}

$c=@'
An agricultural robot can be programmed to find tomato flowers and assist pollination, but a greenhouse is not a factory floor. Leaves hide targets, sunlight changes during the day, and a plant bends after contact. A machine that succeeds in a prepared row may fail when varieties, spacing or humidity change.

Chinese researchers developed four generations of a farming robot after visiting farms in several regions. The machine combines three-dimensional vision with autonomous navigation. Those technical abilities matter because pollination is a sequence: reach the correct plant, identify a suitable flower, approach without damage, act, and then continue safely through a crowded aisle.

The farm therefore belongs inside the laboratory. Design teams need growers to explain what counts as acceptable contact, which failures are costly and when human work is already efficient. A slower robot may be useful at night or during labor shortages, while a fast machine that bruises plants creates hidden losses.

Evaluation should follow an entire growing cycle rather than a short demonstration. Relevant measures include successful pollination, fruit quality, plant damage, energy use, maintenance and the time workers spend rescuing the robot. Results should also be separated by crop variety and greenhouse layout.

Automation does not remove agricultural judgment. Independent seasonal trials should compare the robot with current work under the same crop conditions, including days when weather or disease changes plant behavior. It redistributes human judgment into training data, operating rules and decisions about when a person should intervene. The strongest field robot is not the one that imitates a human gesture most dramatically. It is the one whose behavior remains understandable and useful amid biological variation.
'@
$q=@(
 @('main_idea','Which design lesson organizes the greenhouse discussion?','Field robots must be evaluated within variable farming conditions, not controlled demonstrations.','The farm therefore belongs inside the laboratory.','文章把农场变化视为研发条件，正确项概括全文。'),
 @('detail','What two capabilities were combined in the reported machine?','Three-dimensional vision and autonomous navigation.','The machine combines three-dimensional vision with autonomous navigation.','第二段直接列出视觉与导航能力。'),
 @('word_guess','In this argument, what does redistributes mean?','Moves human judgment into data, rules and intervention choices.','It redistributes human judgment into training data, operating rules and decisions about when a person should intervene.','语境说明判断没有消失，而是转移到系统设计环节。'),
 @('inference','Why might a slower farm robot still create value?','It can work at useful times without causing the damage associated with speed.','A slower robot may be useful at night or during labor shortages, while a fast machine that bruises plants creates hidden losses.','证据对比了可用时段与快速作业的潜在损失。'),
 @('attitude','Which standard would the writer apply after harvest?','Judge performance across a whole cycle using crop, damage, energy and labor evidence.','Evaluation should follow an entire growing cycle rather than a short demonstration.','作者明确反对只看短时展示。')
)
Add-Tech 4 4 'The Greenhouse Refuses a Perfect Demonstration' $c '页面可访问；核验番茄授粉、三维视觉、自主导航、四代原型、跨学科团队和多地农场调研等事实。' $q

$c=@'
A satellite factory in eastern China applies assembly-line ideas to spacecraft that were once treated mainly as individual projects. Standard workstations, digital records and repeated tests can shorten production time while a growing constellation demands many similar units. Yet mass production in space technology is not ordinary repetition.

Each satellite will face vibration during launch, radiation, temperature swings and long periods without physical repair. A small assembly error can therefore remain hidden until replacement is extremely expensive. Standardization is valuable because it makes expected interfaces and procedures visible; it must not become permission to ignore unusual signals.

Production data can connect design with later operation. If engineers record component batches, test results and deviations, an anomaly in orbit can be traced back to other units that may share the risk. This is a digital thread: a continuous record linking requirements, manufacture, testing and service. Its usefulness depends on accurate entries and authority to stop the line.

Scale changes supply-chain responsibility as well. A faster final assembly cannot compensate for inconsistent sensors or delayed electronic parts. Suppliers need common quality definitions, while designers should avoid unnecessary uniqueness that makes replacement difficult. At the same time, excessive uniformity can create common-mode failure, in which one weakness affects many satellites together.

Operators also need a quarantine process when one component batch produces unusual results. The correct goal is repeatable learning. A factory should lower cost and time while allowing evidence from every test and mission to improve the next unit. The achievement is not simply that satellites leave the building more quickly, but that speed remains compatible with traceability, independent checks and controlled variation.
'@
$q=@(
 @('main_idea','What tension defines the space-factory model?','It must combine production speed with traceable reliability and controlled variation.','Operators also need a quarantine process when one component batch produces unusual results. The correct goal is repeatable learning.','全文围绕规模化与航天可靠性之间的张力展开。'),
 @('detail','Which operating hazards await a satellite after production?','Launch vibration, radiation, temperature swings and limited repair access.','Each satellite will face vibration during launch, radiation, temperature swings and long periods without physical repair.','第二段列出在轨与发射环境。'),
 @('word_guess','How is a “digital thread” used here?','As a continuous record joining design, manufacture, tests and service.','This is a digital thread: a continuous record linking requirements, manufacture, testing and service.','冒号后提供了精确定义。'),
 @('inference','Why can extreme uniformity create fleet-wide risk?','The same hidden weakness may appear across many satellites.','excessive uniformity can create common-mode failure, in which one weakness affects many satellites together.','共同模式故障会把单点弱项扩散到批量产品。'),
 @('attitude','What would count as responsible acceleration?','Faster output that preserves stopping authority and independent quality checks.','speed remains compatible with traceability, independent checks and controlled variation.','作者有条件支持提速。')
)
Add-Tech 18 4 'A Satellite Line Must Manufacture Memory' $c '页面可访问；核验东部地区卫星智能制造工厂、批量生产、数字化工位和卫星规模化交付等报道事实。' $q

$c=@'
Satellite constellations promise connectivity across wide areas because many spacecraft can share coverage and hand signals from one unit to another. The attraction is obvious for remote transport, emergency communication and places where ground networks are costly. The architecture, however, turns connection into a coordination problem.

A single satellite follows a predictable path, while a large constellation continuously changes which unit can serve a user. Software must schedule links, avoid interference and move traffic between space and ground stations. Capacity is not simply the number of satellites; it depends on spectrum, gateways, terminal design and how demand is distributed across time and place.

Resilience also has two meanings. Many units can provide alternatives when one fails, reducing dependence on a single spacecraft. Yet shared software, components or control systems may create correlated failure. Diversity in orbital planes and backup routes helps only if operators test scenarios in which several layers fail together.

Expansion imposes responsibilities beyond service quality. Collision avoidance requires reliable tracking and communication among operators. Satellites need plans for safe disposal at the end of useful life. Brightness and radio emissions can affect astronomy, while replacement launches add material and environmental costs. These effects should enter design before the sky becomes crowded.

Access must be evaluated at the user end. A signal over a region is not useful if terminals are unaffordable, power is unreliable or local services cannot use the connection. Demonstrations should measure completed tasks during difficult weather and peak demand, not merely theoretical coverage.

A smart constellation is therefore governed infrastructure rather than a collection of moving antennas. Its intelligence lies in allocating scarce resources, recovering from failures and limiting harm while delivering a service people can actually reach.
'@
$q=@(
 @('main_idea','Which claim best unites orbit management and user access?','A constellation succeeds as governed infrastructure, not by spacecraft count alone.','A smart constellation is therefore governed infrastructure rather than a collection of moving antennas.','末段概括了全篇。'),
 @('detail','What resources besides satellites shape network capacity?','Spectrum, gateways, terminals and the distribution of demand.','it depends on spectrum, gateways, terminal design and how demand is distributed across time and place.','第二段给出容量的多项约束。'),
 @('word_guess','What does “correlated failure” describe?','Several units failing together because they share a weakness.','shared software, components or control systems may create correlated failure.','共同依赖会造成同时故障。'),
 @('inference','Why is theoretical coverage an inadequate service test?','Users may still lack affordable terminals, power or reliable task completion.','A signal over a region is not useful if terminals are unaffordable, power is unreliable or local services cannot use the connection.','覆盖不等于可用服务。'),
 @('attitude','How does the writer view rapid constellation expansion?','As useful only with collision, disposal and public-impact governance.','These effects should enter design before the sky becomes crowded.','作者设置了明确治理条件。')
)
Add-Tech 19 4 'Connectivity from Space Has a Ground Problem' $c '页面可访问；核验中国建设卫星星座以支持空天地连接、通信应用和商业航天发展的报道主线。' $q

$c=@'
China's space station was expected to conduct more than 1,000 research projects, covering life science, materials, medicine and other fields. The number signals opportunity, yet an orbital laboratory faces an unusual scarcity: crew time, power, volume, data links and return capacity must be shared among experiments.

Selection therefore shapes knowledge. A project may be scientifically interesting but poorly suited to microgravity, or it may require equipment that prevents several smaller studies from flying. Review should ask what the space environment uniquely contributes and whether the result can be compared with a strong ground control.

Large inventories also create a reproducibility challenge. Hardware may differ between missions, astronauts cannot repeat every manual step exactly, and launch schedules delay correction. Protocols should record temperature, vibration, timing and deviations in enough detail for later teams to interpret a result. Negative findings deserve preservation because repeating an unreported failure wastes rare capacity.

Research portfolios need balance. Some experiments seek immediate applications, such as better materials or medical insight; others investigate basic processes whose value may emerge much later. Requiring quick commercial return from every project would distort the station's role. Conversely, a famous scientific label should not protect work from review.

Public communication should distinguish an experiment launched, completed and independently interpreted. Counting a planned project as an achievement confuses access with knowledge. Open metadata and carefully timed data release can allow researchers outside the original team to test conclusions while respecting legitimate safety constraints.

The station's scientific importance is thus not proportional to its project total. It depends on a transparent system that allocates scarce orbital conditions, records failures and converts physical access into evidence that other scientists can question and build upon.
'@
$q=@(
 @('main_idea','What makes a thousand orbital projects scientifically meaningful?','Transparent selection, reproducible records and evidence open to later scrutiny.','It depends on a transparent system that allocates scarce orbital conditions, records failures and converts physical access into evidence that other scientists can question and build upon.','结尾直接给出评价框架。'),
 @('detail','Which constraints must experiments share aboard the station?','Crew time, power, physical space, data links and return capacity.','crew time, power, volume, data links and return capacity must be shared among experiments.','首段列出稀缺资源。'),
 @('word_guess','What does “portfolio” mean in the research discussion?','A managed collection of projects with different aims and time horizons.','Research portfolios need balance.','上下文随后对基础与应用项目进行组合配置。'),
 @('inference','Why should negative results remain accessible?','They can prevent later teams from spending rare orbital resources on the same failure.','repeating an unreported failure wastes rare capacity.','证据句说明隐藏失败会导致重复浪费。'),
 @('attitude','Which project-count claim would the author reject?','Treating every planned experiment as completed scientific knowledge.','Counting a planned project as an achievement confuses access with knowledge.','作者区分计划、完成和解释。')
)
Add-Tech 20 4 'A Thousand Experiments Compete for One Orbit' $c '页面可访问；核验空间站计划开展1000余项研究及生命、材料、医学等研究方向。' $q

$c=@'
An inflatable structure tested for use in an orbital factory offers a different answer to a basic space problem: launch vehicles have narrow interiors, while manufacturing may need large working volume. A folded module can travel compactly and expand after reaching orbit. Deployment, however, is only the first requirement.

The structure must retain shape through repeated heating and cooling, resist small debris and provide barriers against radiation and leakage. Flexible materials behave differently from rigid metal when equipment vibrates or when a tool pushes against a wall. Engineers therefore need tests that combine pressure, loads and long duration rather than celebrating maximum volume alone.

Manufacturing in orbit also needs a clear reason. Microgravity and vacuum may enable crystals, alloys or biological products that are difficult to make on Earth. But the benefit must exceed launch, energy, crew, quality-control and return costs. A product whose special property cannot be measured consistently has no reliable market merely because it was made in space.

Automation becomes central when human access is limited. Robots may move materials and inspect products, but remote control faces communication delay and incomplete sensory information. Systems should fail safely, isolate a damaged process and preserve diagnostic records. Repair plans must identify which parts can be replaced and which failure would end the mission.

An inflatable factory also raises governance questions. Experiments, commercial production and crew safety may compete for power or attention. Ownership of data, responsibility for debris and verification of product claims need rules before production expands.

The useful innovation is not simply a larger room created from a smaller package. It is a test of whether expandable architecture can become dependable industrial infrastructure under conditions where maintenance, rescue and waste disposal are unusually difficult.
'@
$q=@(
 @('main_idea','What question does the inflatable-factory test ultimately raise?','Whether expandable volume can become reliable infrastructure under orbital constraints.','It is a test of whether expandable architecture can become dependable industrial infrastructure under conditions where maintenance, rescue and waste disposal are unusually difficult.','末句统领全文。'),
 @('detail','Why is folding the module useful at launch?','It fits a large future workspace into a narrow launch interior.','A folded module can travel compactly and expand after reaching orbit.','首段说明折叠与展开的关系。'),
 @('word_guess','What does “isolate” mean in the failure plan?','Contain a damaged process so it does not spread harm.','Systems should fail safely, isolate a damaged process and preserve diagnostic records.','与安全失效和诊断记录并列，可知指隔离故障。'),
 @('inference','Why is a unique orbital product not automatically commercial?','Its special property must be measurable and justify full production and return costs.','A product whose special property cannot be measured consistently has no reliable market merely because it was made in space.','稀缺性不能替代质量与成本证据。'),
 @('attitude','What is the authors view of the successful deployment itself?','Necessary but far from sufficient evidence of an orbital factory.','Deployment, however, is only the first requirement.','作者明确限定展开只是首步。')
)
Add-Tech 21 4 'The Inflatable Factory Must Survive Its Own Success' $c '页面可访问；核验充气式空间工厂试验、在轨展开和空间制造设想等报道事实。' $q

$c=@'
A robotics innovation center in Shanghai signed training agreements with technology companies, creating access to more settings in which machines can learn. The shift sounds simple—from making a robot walk to making it work—but “work” is defined by particular environments, people and consequences.

A warehouse values predictable handling and safe movement around workers. A care setting requires gentler contact, privacy and clear human authority. A factory may prioritize repeatable precision, while a public venue confronts children, crowds and unexpected objects. Training across scenes can broaden a robot's experience, yet combining data without labels may blur distinctions that safety depends on.

Partnerships should specify more than the number of collected demonstrations. Who chooses tasks? Which failures are retained? Can workers refuse recording? How are trade secrets and personal information separated from motion data? An open training ecosystem is credible only when access rules and later use are visible to contributors.

Benchmarking also changes as robots leave controlled floors. Average task success can hide rare high-cost events. Evaluators need distributions, near misses, recovery behavior and performance after maintenance. A model that completes ninety-nine easy lifts but mishandles one dangerous object may be less useful than a slower system that asks for help.

Agreements can accelerate learning because no single laboratory contains every realistic condition. They can also concentrate power if a shared center becomes the only route to data or certification. Common interfaces, portable records and opportunities for independent testing keep collaboration from becoming dependence.

Longitudinal review should ask whether performance survives software updates and staff turnover, rather than ending when a partnership announces its first dataset. The strongest ecosystem does not merely feed more experiences into machines. It preserves the meaning and ownership of those experiences, then uses them to decide where autonomy is justified and where human control should remain immediate.
'@
$q=@(
 @('main_idea','Which responsibility accompanies a multi-scene robot training network?','It must preserve context, rights and safety meaning while sharing experience.','It preserves the meaning and ownership of those experiences, then uses them to decide where autonomy is justified and where human control should remain immediate.','结尾概括了生态合作的责任。'),
 @('detail','Why can warehouse and care data not be treated as identical?','Their contact, privacy, authority and risk requirements differ.','A care setting requires gentler contact, privacy and clear human authority.','场景差异决定数据含义。'),
 @('word_guess','In this passage, what is a “near miss”?','A dangerous event narrowly avoided rather than a completed failure.','Evaluators need distributions, near misses, recovery behavior and performance after maintenance.','该词与故障和恢复并列，指险些发生的事故。'),
 @('inference','Why might a robot that requests help outperform a faster one?','Safe escalation can matter more than average speed on easy cases.','A model that completes ninety-nine easy lifts but mishandles one dangerous object may be less useful than a slower system that asks for help.','作者强调低频高损害风险。'),
 @('inference','How could one shared center create unhealthy dependence?','It might control the only route to important data or certification.','They can also concentrate power if a shared center becomes the only route to data or certification.','证据直接支撑该推断。')
)
Add-Tech 5 5 'A Robot Learns a Workplace, Not a Generic World' $c 'China Daily页面可访问；核验上海机器人创新中心签署训练场合作、从行走向工作能力转变、多场景训练及开放协作等事实。' $q

$c=@'
China's commercial space sector connects launch providers, satellite makers, ground services, data companies and specialized investors. Its expansion is often summarized by launch counts or financing rounds. Those measures reveal activity, but an industrial system becomes durable only when customers receive dependable services and failures produce shared learning.

Commercial incentives can shorten schedules and encourage component reuse. They can also reward optimistic claims before long-term reliability is known. Procurement should therefore separate demonstration contracts from operational service. A buyer testing a new system can accept uncertainty; an emergency user needs explicit availability, backup and compensation rules.

Launch capacity is a bottleneck with unusual consequences. Delays at one vehicle can strand satellites, staff and capital across several firms. More launchers may reduce queues, yet standard interfaces and transparent schedules can sometimes create greater resilience than another proprietary system. Infrastructure should be judged by how well participants can switch when one route fails.

Insurance and investigation determine whether risk becomes knowledge. If accident data remains hidden behind commercial secrecy, other operators may repeat the same design error. Public reporting need not expose every trade secret, but it should describe causes, affected components and corrective action well enough to protect the wider sector.

Environmental responsibility extends beyond the launch site. Manufacturing uses materials and energy; rocket stages and satellites create disposal duties; constellations affect orbital congestion. Firms need lifecycle plans whose costs are not transferred to future operators or the public.

Government still shapes the market through spectrum, safety, procurement and research. The challenge is to support experimentation without guaranteeing individual business models. Neutral standards and competitive access allow unsuccessful firms to exit without taking essential services with them.

Commercial space reaches new heights when competition strengthens a common technical foundation. A busy market is a beginning; reliable service, open failure learning and accountable end-of-life design show whether the sector has become infrastructure.
'@
$q=@(
 @('main_idea','What distinguishes a busy commercial-space market from mature infrastructure?','Reliable service, shared failure learning and accountable lifecycle duties.','A busy market is a beginning; reliable service, open failure learning and accountable end-of-life design show whether the sector has become infrastructure.','结尾给出成熟标准。'),
 @('detail','Which actors form the sector described at the start?','Launch, satellite, ground-service, data and investment organizations.','China''s commercial space sector connects launch providers, satellite makers, ground services, data companies and specialized investors.','首句列举产业链参与者。'),
 @('word_guess','What does “bottleneck” mean in the launch discussion?','A constrained stage that delays many connected activities.','Launch capacity is a bottleneck with unusual consequences.','后文说明一个环节延误会牵连多家公司。'),
 @('inference','Why should accident findings cross company boundaries?','Otherwise similar hidden errors may be repeated by other operators.','If accident data remains hidden behind commercial secrecy, other operators may repeat the same design error.','证据说明公开失败信息的公共价值。'),
 @('inference','Why favor neutral standards over protection of one firm?','Essential services can continue even when an individual business model fails.','Neutral standards and competitive access allow unsuccessful firms to exit without taking essential services with them.','标准可降低单家公司退出的系统冲击。')
)
Add-Tech 22 5 'Commercial Space Needs a Way to Fail Well' $c '页面可访问；核验商业航天产业链、发射与卫星制造、应用服务和投融资发展等报道主线。' $q

$c=@'
A roadmap for upgrading artificial intelligence and new-energy vehicles links two industries that increasingly depend on one another. Vehicles generate data and need chips, models, sensors and software; AI systems gain a demanding physical environment in which errors affect motion and safety. Integration can create value, but it also connects risks that were once easier to separate.

Industrial roadmaps are useful when they coordinate standards, infrastructure and research horizons. They become misleading when targets are treated as forecasts guaranteed by policy. Battery chemistry, computing cost, consumer demand and international supply conditions can change before factories built today reach full output.

Software updates complicate product responsibility. A car can acquire new behavior after sale, so safety assessment cannot end at the factory gate. Version records, staged release, rollback and monitoring of rare events should form part of certification. Drivers need intelligible explanations of what changed rather than a general notice that the system became smarter.

Data creates another boundary problem. Fleet information can improve maps, energy use and hazard detection, but location and cabin records may expose individuals. Collection should be proportional to a stated function, with retention limits and realistic deletion routes. Training value is not permission for indefinite storage.

Upgrading also affects repair networks and workers. Independent workshops may lose access if diagnostics are locked behind proprietary software. Technicians need training for high-voltage systems and algorithmic fault reports. A technologically advanced vehicle that cannot be safely maintained outside a few cities creates unequal reliability.

The roadmap should therefore be evaluated through capability, not labels. Are systems safer after updates? Can suppliers replace constrained components? Do repairers receive usable information? Are efficiency gains measured across the battery and electricity lifecycle?

AI and vehicle manufacturing advance together when coordination preserves modularity and accountability. Deep integration should make failures easier to locate and correct, not turn every component into part of an opaque promise.
'@
$q=@(
 @('main_idea','What condition makes AI–vehicle integration responsible?','Coordination must preserve traceability, repairability and accountable system boundaries.','Deep integration should make failures easier to locate and correct, not turn every component into part of an opaque promise.','末句表达中心判断。'),
 @('detail','Which controls should accompany vehicle software updates?','Version records, staged release, rollback and rare-event monitoring.','Version records, staged release, rollback and monitoring of rare events should form part of certification.','第三段直接列出控制措施。'),
 @('word_guess','What does “proportional” mean for vehicle data collection?','Limited to what a declared function reasonably requires.','Collection should be proportional to a stated function, with retention limits and realistic deletion routes.','语境强调目的限定与最小收集。'),
 @('inference','Why could locked diagnostics produce unequal reliability?','Independent repairers and users outside major centers may lack safe maintenance.','A technologically advanced vehicle that cannot be safely maintained outside a few cities creates unequal reliability.','维修可达性决定技术能否普遍可靠。'),
 @('inference','Why are roadmap targets not guaranteed forecasts?','Technology costs, demand and supply conditions can change before investments mature.','Battery chemistry, computing cost, consumer demand and international supply conditions can change before factories built today reach full output.','多个变量会改变既定路径。')
)
Add-Tech 23 5 'When Two Smart Industries Share One Failure' $c '页面可访问；核验2026年AI与新能源汽车产业升级路线图、技术融合和产业链协同等报道事实。' $q

$c=@'
At a supply-chain expo, aviation meets innovation through aircraft, components, digital systems, materials and services displayed by organizations that rarely appear in one public room. The encounter can reveal dependency: a new airframe may rely on specialized alloys, certification software, maintenance data and suppliers several tiers away from the final producer.

Visibility is not the same as resilience. A colorful map of partners shows who participates under normal conditions, while resilience asks what happens after disruption. Firms need to know which components lack substitutes, how long inventories last and whether an alternative supplier can meet certification requirements without restarting years of testing.

Aviation makes substitution difficult because safety evidence belongs partly to a specific design and process. A chemically similar material is not automatically equivalent if manufacturing changes fatigue behavior. Digital twins and shared standards can accelerate comparison, but they cannot replace physical validation where consequences are severe.

Expos can support early coordination. Suppliers can understand future demand, smaller firms can demonstrate specialized capability, and manufacturers can identify hidden concentration. Yet public announcements may encourage companies to exaggerate readiness. Procurement should use staged qualification rather than assume that a signed intention equals deliverable capacity.

Data sharing requires boundaries. Maintenance records can reveal common defects, but they may contain commercial and operationally sensitive information. Sector-wide learning needs agreed formats, anonymization where possible and clear authority to issue safety notices.

Resilience also includes workforce and tools. Periodic drills can expose documentation that looks complete but cannot guide a real repair. A substitute part is useless if technicians lack procedures or inspection equipment. Training, documentation and calibration capacity should travel with the component.

The expo is most valuable as a place to ask dependency questions before a crisis. Innovation enters aviation responsibly when novelty is connected to certification evidence, maintainable skills and multiple credible routes through the chain.
'@
$q=@(
 @('main_idea','What does the aviation expo reveal beyond new products?','Hidden dependencies must be tested for substitution, certification and maintenance.','The expo is most valuable as a place to ask dependency questions before a crisis.','全文从展示转向供应链韧性。'),
 @('detail','Why is a chemically similar material not automatically replaceable?','Its manufacturing process may change fatigue and safety behavior.','A chemically similar material is not automatically equivalent if manufacturing changes fatigue behavior.','第三段说明航空替代需重新验证。'),
 @('word_guess','What does “qualification” mean in procurement?','A staged process proving that a supplier or part meets requirements.','Procurement should use staged qualification rather than assume that a signed intention equals deliverable capacity.','该词与交付能力核验相连。'),
 @('inference','Why must training accompany an alternative component?','Technicians need procedures and calibrated tools to use it safely.','A substitute part is useless if technicians lack procedures or inspection equipment.','零件可得不等于可安全维护。'),
 @('inference','Why can a partner map overstate resilience?','It describes normal participation without showing behavior during disruption.','A colorful map of partners shows who participates under normal conditions, while resilience asks what happens after disruption.','作者区分可见关系与压力下表现。')
)
Add-Tech 24 5 'Aviation Resilience Begins Below the Final Aircraft' $c '页面可访问；核验供应链博览会航空链展区、整机与零部件、材料和数字创新协同展示等事实。' $q

$c=@'
Artificial intelligence can help an energy-storage operator forecast demand, predict renewable output, schedule charging and identify abnormal battery behavior. These tasks connect data with electricity, but the word “optimize” hides a choice: the system must decide which objective matters when cost, carbon, battery life and grid stability point in different directions.

A controller trained to minimize short-term price may cycle batteries aggressively, accelerating degradation. One designed to protect battery life may hold energy during a grid emergency. Objectives need explicit priorities and constraints set by accountable operators, not silently inferred from historical data.

Forecast uncertainty should travel into decisions. A single predicted curve encourages false confidence; probability ranges allow the system to reserve capacity for plausible errors. Operators should test extreme heat, communication loss and unusual demand, because average accuracy does not describe performance during the hours storage is most valuable.

Battery data requires interpretation. Temperature or voltage patterns may indicate danger, normal aging or a faulty sensor. An AI alert should support inspection rather than automatically assign cause. Records of false alarms and missed events are necessary to calibrate trust and decide when human confirmation is required.

Market design shapes the algorithm. Payments for fast response, capacity or energy can reward different behavior. If rules encourage several services at once, software may promise the same stored unit to incompatible commitments. Verification should reconcile market schedules with the physical state of charge.

Cybersecurity joins physical safety because remote commands can move large amounts of power. Access control, signed updates, offline fallback and manual isolation must be tested as operating functions, not policy documents.

The synergy between AI and storage is real when prediction improves disciplined control. Intelligence does not remove trade-offs; it makes them executable at speed. That increases the need to state objectives, preserve override and audit how each high-impact decision was made.
'@
$q=@(
 @('main_idea','What is the central governance problem in AI-controlled storage?','Fast optimization must expose objectives, uncertainty, overrides and auditability.','That increases the need to state objectives, preserve override and audit how each high-impact decision was made.','末句概括核心责任。'),
 @('detail','Which operating tasks can AI assist in the storage system?','Forecasting, charge scheduling and abnormal-behavior detection.','Artificial intelligence can help an energy-storage operator forecast demand, predict renewable output, schedule charging and identify abnormal battery behavior.','首句列出主要任务。'),
 @('word_guess','What does “calibrate trust” mean in the alert context?','Adjust reliance using evidence about false and missed warnings.','Records of false alarms and missed events are necessary to calibrate trust and decide when human confirmation is required.','通过错误记录调整信任程度。'),
 @('inference','Why are probability ranges safer than one forecast curve?','They let operators reserve capacity for plausible prediction errors.','probability ranges allow the system to reserve capacity for plausible errors.','不确定性范围支持预留。'),
 @('inference','How could market software promise physically impossible service?','It may commit the same stored energy to incompatible products.','software may promise the same stored unit to incompatible commitments.','市场承诺必须与实际荷电状态对账。')
)
Add-Tech 25 5 'An Intelligent Battery Still Needs Declared Priorities' $c '页面可访问；核验AI与电力系统协同推动储能预测、调度、运维和产业发展的报道主线。' $q

$c=@'
More than 500 firms registered for the 2026 China International Supply Chain Expo, indicating that supply-chain cooperation remains attractive despite uncertainty in trade and technology. Participation is easy to count; the harder question is what exhibitors can learn about dependencies that ordinary purchasing records do not reveal.

A final manufacturer often knows its direct suppliers but has limited visibility several tiers upstream. A small producer of a specialized chemical, chip tool or connector may serve many apparently unrelated products. If that node fails, diversification at the first tier offers little protection. Mapping should therefore follow critical functions and materials rather than company names alone.

Visibility can create new risk. Detailed maps contain commercial secrets and may expose vulnerable facilities. A trusted system needs graduated access: firms share enough data for safety and continuity without publishing every price or design. Public authorities may require broader information for emergencies, accompanied by controls on later use.

Resilience metrics must resist theatrical redundancy. Two suppliers located in the same flood zone or dependent on the same electricity substation are not truly independent. Alternative routes should be tested for capacity, certification and time to activate. Inventory helps only within its shelf life and financing limits.

An expo can make coordination cheaper by bringing unfamiliar firms together, but signed agreements remain options rather than operational capability. Scenario exercises after the event can reveal whether contacts, data formats and decision rights work under pressure. Results should identify delays and conflicts, not merely confirm that every participant attended.

Efficiency and resilience need not be enemies. Standard components and shared logistics can lower cost while enabling substitution. Yet extreme concentration may produce scale today and fragility tomorrow. The acceptable balance depends on the social cost of interruption, which is higher for medicine or power equipment than for optional consumer products.

The value of 500 registrations lies in the network they could help examine. A supply-chain gathering becomes infrastructure only when it turns introductions into verified alternatives, bounded information sharing and collective preparation for failures that no company can manage alone.
'@
$q=@(
 @('main_idea','What would transform expo participation into genuine resilience?','Verified alternatives, bounded information sharing and joint preparation for disruption.','A supply-chain gathering becomes infrastructure only when it turns introductions into verified alternatives, bounded information sharing and collective preparation for failures that no company can manage alone.','末句给出转化条件。'),
 @('detail','What participation figure anchors the discussion?','More than 500 registered firms.','More than 500 firms registered for the 2026 China International Supply Chain Expo','首句提供数量事实。'),
 @('word_guess','What is “theatrical redundancy” in this context?','Alternatives that look separate but share the same hidden failure.','Two suppliers located in the same flood zone or dependent on the same electricity substation are not truly independent.','语境批评表面上的备份。'),
 @('inference','Why should critical-function maps extend beyond direct suppliers?','A small upstream node may support many products and defeat first-tier diversification.','If that node fails, diversification at the first tier offers little protection.','上游共用节点可能造成系统性中断。'),
 @('inference','Why should resilience standards vary by product?','The social cost of interrupted medicine or power equipment is unusually high.','The acceptable balance depends on the social cost of interruption, which is higher for medicine or power equipment than for optional consumer products.','关键产品中断后果不同。')
)
Add-Tech 26 6 'Five Hundred Firms Can Still Share One Weak Link' $c '页面可访问；核验500余家企业报名2026链博会及其国际供应链合作背景。' $q

$c=@'
The boom in artificial-intelligence computing power travels upstream through chips, servers, optical links, cooling systems, electricity networks and construction. Demand at one layer can create bottlenecks several layers away, so a record for installed computing capacity does not describe the cost or usefulness of the full system.

Accelerator chips receive attention, yet utilization determines whether scarce equipment produces value. A cluster may be technically large while jobs wait because software, memory or network communication cannot keep processors busy. Reporting useful work per unit of energy can reveal more than peak theoretical performance, although useful work must be defined for different applications.

The physical chain has geographic consequences. Data centers may locate near affordable electricity or cool climates, while users value low delay and access to skilled operators. Moving computation can reduce one cost and increase transmission, network or water pressure elsewhere. Regional planning should treat computing loads as industrial infrastructure rather than invisible internet activity.

Rapid purchasing creates a cycle risk. Firms may order equipment based on projected demand, encouraging suppliers to expand capacity just as algorithms become more efficient or customers consolidate. Long-lived power and cooling assets can then outlast the chips that justified them. Modular construction and staged investment preserve options under uncertain growth.

Concentration affects both innovation and security. A narrow set of component providers can improve compatibility but magnify disruption. Substitution requires software support, testing and developer skills, not merely another chip with similar specifications. Open interfaces reduce switching cost only when implementations remain interoperable in practice.

Environmental accounting must include embodied materials, electricity source, water use and retired equipment. Public comparisons should state system boundaries. Efficiency gains can be consumed by larger models or more frequent requests, an effect that makes absolute resource totals necessary beside per-task measures.

Computing power is productive capacity, not a product outcome. The industrial chain creates lasting value when hardware is well utilized, applications justify resource use and investment can adapt without leaving communities with stranded infrastructure or hidden environmental liabilities.
'@
$q=@(
 @('main_idea','How should an AI computing boom be judged across its chain?','By useful, adaptable capacity and total resource consequences, not installed hardware alone.','The industrial chain creates lasting value when hardware is well utilized, applications justify resource use and investment can adapt without leaving communities with stranded infrastructure or hidden environmental liabilities.','结尾建立综合标准。'),
 @('detail','Which upstream systems are named besides processors?','Servers, optical links, cooling, electricity and construction.','The boom in artificial-intelligence computing power travels upstream through chips, servers, optical links, cooling systems, electricity networks and construction.','首段列出产业链。'),
 @('word_guess','What are “stranded” assets in the final paragraph?','Infrastructure left underused after the demand or technology changes.','Long-lived power and cooling assets can then outlast the chips that justified them.','前文解释长期设施可能失去原用途。'),
 @('inference','Why may a large cluster still leave AI jobs waiting?','Memory, software or network limits can keep processors idle.','A cluster may be technically large while jobs wait because software, memory or network communication cannot keep processors busy.','算力规模受其他环节制约。'),
 @('inference','Why are per-task efficiency numbers insufficient?','Greater model size and usage can raise absolute resource consumption.','Efficiency gains can be consumed by larger models or more frequent requests','反弹效应会抵消单位效率。')
)
Add-Tech 27 6 'The AI Chip Is Only the Visible Bottleneck' $c '页面可访问；核验AI算力增长带动芯片、服务器、光互联、液冷和电力等上游产业链的报道主线。' $q

$c=@'
A five-year blueprint can place advanced aircraft engines, fusion research and lunar exploration under one national account of future capability. These projects differ radically in maturity and uncertainty, so the common label “mega-project” should describe governance scale rather than imply that each follows the same path to success.

Aircraft engines develop through repeated design, materials testing, manufacturing control and long operational validation. Fusion experiments may produce scientific knowledge even when commercial power remains distant. Lunar missions combine launch reliability, navigation, surface operations and scientific priorities under narrow windows. A milestone appropriate to one field can be meaningless in another.

Portfolio governance must therefore separate mission goals, learning goals and industrial goals. A demonstrator may test one risky component without promising a complete product. A research facility can build measurement capacity that later programs use. Procurement can develop suppliers, but premature production targets may freeze an immature design.

Large projects create coordination advantages and political hazards. Stable funding supports long experiments and specialized teams. The same visibility can make managers reluctant to report delay or negative results. Independent technical review, documented decision gates and protected routes for dissent help distinguish persistence from escalation of commitment.

Spillovers should be demonstrated rather than assumed. Advanced materials or control systems may benefit other industries, but only if knowledge, standards and trained people can move. Security restrictions can be necessary while still allowing non-sensitive methods and safety findings to circulate.

Opportunity cost belongs in the evaluation. Money, facilities and expert attention committed to one project cannot serve every alternative. This does not reduce strategic science to a short-term financial return; it requires leaders to state why a project deserves scarce resources and what evidence would justify redesign or termination.

Ambition is credible when uncertainty is organized instead of hidden. The blueprint should allow aircraft, fusion and lunar work to be compared on governance quality—clear purposes, honest milestones, learning from failure and revisable commitment—without forcing their scientific outcomes onto one artificial timetable.
'@
$q=@(
 @('main_idea','What common standard can govern very different mega-projects?','Clear purposes, field-appropriate milestones, failure learning and revisable commitment.','The blueprint should allow aircraft, fusion and lunar work to be compared on governance quality—clear purposes, honest milestones, learning from failure and revisable commitment—without forcing their scientific outcomes onto one artificial timetable.','末段给出跨领域共同标准。'),
 @('detail','Why are identical milestones unsuitable for the three fields?','They differ in maturity, experiment type and route to usable outcomes.','These projects differ radically in maturity and uncertainty','开头即说明差异。'),
 @('word_guess','What does “escalation of commitment” imply?','Continuing a failing course mainly because much has already been invested.','help distinguish persistence from escalation of commitment.','该短语与理性坚持形成对照。'),
 @('inference','Why can early production targets damage innovation?','They may lock suppliers and engineers into an immature design.','premature production targets may freeze an immature design.','证据直接支持。'),
 @('inference','Why must spillovers be traced instead of announced?','Benefits require knowledge, standards and skilled people to move into other uses.','only if knowledge, standards and trained people can move.','外溢需实际传递机制。')
)
Add-Tech 28 6 'Mega-Projects Need Different Clocks' $c '页面可访问；核验五年规划提出先进航空发动机、聚变和探月等重大科技工程的报道事实。' $q

$c=@'
A roadmap for a Beautiful China can include technological systems for monitoring pollution, modeling ecosystems, managing energy and supporting enforcement. Technology makes conditions visible at greater speed and scale, but a sensor-rich administration is not automatically a more accountable one.

Monitoring networks embed choices about location, frequency and variables. A dense urban network may detect street-level exposure while rural soil or biodiversity remains poorly observed. Algorithms trained on abundant data can then reinforce the imbalance by appearing more confident where investment was already highest. Data gaps should be represented as uncertainty, not silently filled with convenient averages.

Remote sensing and automated alerts can direct inspectors toward unusual events. They can also create false precision. A satellite signal may indicate vegetation stress without identifying its cause; an emissions anomaly can reflect equipment failure rather than illegal activity. Enforcement requires corroboration, procedural fairness and a record of how automated evidence influenced a decision.

Interoperability matters because air, water, land and energy systems cross agencies. Shared identifiers and standards can connect evidence, yet centralization raises security and mission-creep concerns. Access should follow role and purpose, with logs that allow later audit. Public dashboards need explanations of revision and uncertainty rather than decorative real-time numbers.

Technology procurement should include maintenance and exit. Sensors drift, models become outdated and vendors may disappear. Agencies need calibration plans, portable data and the ability to replace a system without losing historical comparability. A cheap pilot can become expensive dependence if these conditions are omitted.

Citizen reports and local knowledge remain valuable because formal networks cannot observe every pathway. Their evidence needs verification, but excluding it may hide problems that standard stations were never designed to see. Participation also gives affected communities a way to question priorities.

Digital tools contribute to environmental beauty when they strengthen contestable evidence: claims can be checked, uncertainty located and decisions appealed. The roadmap should treat computation as part of public measurement infrastructure, governed with the same care as the environmental actions it informs.
'@
$q=@(
 @('main_idea','What makes environmental technology publicly accountable?','It must produce contestable evidence with visible uncertainty, audit and appeal.','Digital tools contribute to environmental beauty when they strengthen contestable evidence: claims can be checked, uncertainty located and decisions appealed.','末段明确提出公共问责标准。'),
 @('detail','Which maintenance risks can weaken a monitoring system?','Sensor drift, outdated models and disappearing vendors.','Sensors drift, models become outdated and vendors may disappear.','第五段列举运行风险。'),
 @('word_guess','What does “mission creep” mean for shared environmental data?','Data gradually being used beyond its original authorized purpose.','centralization raises security and mission-creep concerns.','与目的和角色限制相对，指用途扩张。'),
 @('inference','Why can more urban data deepen geographic imbalance?','Algorithms become confident where observation is dense while rural gaps remain hidden.','Algorithms trained on abundant data can then reinforce the imbalance by appearing more confident where investment was already highest.','数据密度影响模型置信度。'),
 @('inference','Why should automated alerts not directly trigger punishment?','Signals may have alternative causes and require corroboration and fair procedure.','Enforcement requires corroboration, procedural fairness and a record of how automated evidence influenced a decision.','自动信号不是充分法律事实。')
)
Add-Tech 29 6 'A Beautiful Dashboard Can Still Hide a Blind Spot' $c '页面可访问；核验美丽中国未来五年路线图及数字监测、绿色转型和环境治理技术应用的报道主线。' $q

$c=@'
Lithium batteries are difficult air cargo because a damaged or defective cell can enter thermal runaway, releasing heat that triggers neighboring cells. China reported a successful debut of safety technology for such cargo in 2025. A successful trial is important, but aviation safety depends on layers that remain effective when assumptions fail.

Prevention begins before loading. Manufacturers and shippers need accurate classification, state-of-charge rules, packaging and records that identify recalls or damage. Detection during transport must distinguish a dangerous trend from normal temperature variation quickly enough for action. Containment then aims to slow propagation, limit smoke or heat and protect aircraft systems.

No single test can cover every battery chemistry, size, packaging arrangement and hidden defect. Certification should define the tested envelope: the conditions under which evidence supports a claim. Operations outside that envelope require new analysis rather than confidence borrowed from a related product.

Human factors remain decisive. Ground staff must recognize damaged packages and resist schedule pressure to accept uncertain declarations. Flight crews need alerts that indicate both severity and available response, not a stream of raw sensor values. Training should include ambiguous cases and coordination with airports after diversion.

Data sharing confronts commercial and safety interests. Incident reports may reveal supplier defects or shipping routes, yet delayed warning can expose other carriers. A protected reporting system can separate blame from urgent hazard communication while preserving investigation rights.

Security must also be considered if monitoring devices communicate wirelessly or feed automated cargo decisions. Authentication, software updates and offline procedures prevent a cyber fault from creating a physical blind spot. Equipment should fail visibly rather than report reassuring but stale data.

The debut technology deserves confidence proportional to its evidence. Regulators should also track whether packaging and declaration practices change after deployment. Long-term success requires independent tests, diverse cargo scenarios, maintenance records and proof that crews can use the system under time pressure. Safety innovation is mature when it joins prevention, detection, containment and learning without allowing any layer to become an excuse for weakening the others.
'@
$q=@(
 @('main_idea','How should new lithium-cargo safety technology earn lasting confidence?','Through layered prevention, detection, containment, human use and incident learning.','Safety innovation is mature when it joins prevention, detection, containment and learning without allowing any layer to become an excuse for weakening the others.','末句总结分层安全。'),
 @('detail','What is thermal runaway in the described cargo risk?','Self-amplifying heat from a cell that can spread to neighboring batteries.','a damaged or defective cell can enter thermal runaway, releasing heat that triggers neighboring cells.','首段解释该现象。'),
 @('word_guess','What is the tested “envelope”?','The range of conditions for which a safety claim has supporting evidence.','the conditions under which evidence supports a claim.','冒号后给出定义。'),
 @('inference','Why should monitoring equipment fail visibly?','Silent stale data could falsely reassure crews during a hazard.','Equipment should fail visibly rather than report reassuring but stale data.','隐蔽故障会制造错误安全感。'),
 @('inference','Why are raw sensor streams inadequate for crews?','Time-critical decisions require interpreted severity and available responses.','Flight crews need alerts that indicate both severity and available response, not a stream of raw sensor values.','信息必须转化为行动提示。')
)
Add-Tech 30 6 'Battery Cargo Safety Is a Chain of Honest Signals' $c '页面可访问；核验2025年锂电池航空货运安全技术成功首秀及其面向运输安全的报道事实。' $q

$out=[IO.Path]::Combine([IO.Path]::GetTempPath(),'technology-l4-l6-manual.json')
$items|ConvertTo-Json -Depth 12|Set-Content $out -Encoding UTF8
Write-Host ('wrote {0} passages' -f $items.Count)

