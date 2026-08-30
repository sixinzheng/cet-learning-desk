$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$manifest = Get-Content (Join-Path $root 'seed\reading_source_manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$sample = Get-Content (Join-Path $root 'seed\review_batches\culture_environment_sample.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$items = [System.Collections.Generic.List[object]]::new()
$adapt = '题材参考所列新华社英文网公开信息；本站围绕独立中心问题重组事实并原创改写，非媒体原文，非历年真题。'

function New-Questions {
  param($Number,$Level,$Title,$Main,$MainEvidence,$DetailPrompt,$Detail,$DetailEvidence,$Term,$Meaning,$TermEvidence,$Inference,$InferenceEvidence,$Final,$FinalEvidence)
  $defs = @(
    @('main_idea',"Central reading: ${Title}?",$Main,$MainEvidence),
    @('detail',$DetailPrompt,$Detail,$DetailEvidence),
    @('word_guess',"Define $Term in context.",$Meaning,$TermEvidence),
    @('inference',"Infer the consequence of $Term.",$Inference,$InferenceEvidence),
    @($(if($Level -ge 5){'inference'}else{'attitude'}),"Assess the ending through $Term.",$Final,$FinalEvidence)
  )
  $wrong = @(
    "The evidence proves that every environmental problem has already been solved.",
    "One reported number makes local conditions and later monitoring irrelevant.",
    "Public participation can be replaced completely by a single machine.",
    "The source supports an unlimited conclusion beyond the case described.",
    "Short-term visibility matters more than the system that produces lasting results.",
    "Environmental gains should be judged without considering costs or trade-offs."
  )
  $list=[System.Collections.Generic.List[object]]::new()
  for($i=0;$i -lt 5;$i++){
    $d=$defs[$i]; $pos=($Number+$i)%4; $opts=[System.Collections.Generic.List[string]]::new(); $k=0
    for($j=0;$j -lt 4;$j++){ if($j -eq $pos){$opts.Add($d[2])}else{$opts.Add($wrong[($Number+$i+$k)%$wrong.Count]);$k++} }
    $list.Add([ordered]@{type=$d[0];question=$d[1];options=$opts;answer='ABCD'[$pos].ToString();explanation="《$Title》的证据句直接限定了正确项；其他选项把个案扩大为普遍结论，或忽略文中条件。";evidence_text=$d[3]})
  }
  return $list
}

function Add-Env {
  param($Number,$Level,$Title,$Content,$Verification,$Main,$MainEvidence,$DetailPrompt,$Detail,$DetailEvidence,$Term,$Meaning,$TermEvidence,$Inference,$InferenceEvidence,$Final,$FinalEvidence,$Url='',$SourceTitle='',$Date='')
  $sid="src-环境-$('{0:D2}' -f $Number)"; $meta=$manifest|Where-Object source_id -eq $sid|Select-Object -First 1
  $qs=New-Questions $Number $Level $Title $Main $MainEvidence $DetailPrompt $Detail $DetailEvidence $Term $Meaning $TermEvidence $Inference $InferenceEvidence $Final $FinalEvidence
  $items.Add([ordered]@{corpus_id="cet-human-environment-l$Level-$('{0:D2}' -f $Number)";source_id=$sid;title=$Title;topic='环境';difficulty=$Level;source_name='新华社英文网';source_url=if($Url){$Url}else{$meta.source_url};source_title=if($SourceTitle){$SourceTitle}else{$meta.source_title};source_published_at=if($Date){$Date}else{$meta.source_published_at};retrieved_at='2026-08-29';source_verification=$Verification;adaptation_note=$adapt;content=$Content.Trim();questions=$qs})
}

# Preserve the five hand-reviewed environment baselines as the first article in levels 1-5.
$verify = @{
  1='页面可访问；核验白皮书发布日期、2030年前碳达峰和2060年前碳中和目标，以及能源、工业、交通、建筑、循环经济和碳汇等多路径框架。'
  2='图片报道页面可访问；核验海尾国家湿地公园修复后重新开放，以及监测记录到213种鸟类。'
  3='页面可访问；核验废旧电缆、厨余处理和二手流通案例及报道中的有限数量事实。'
  4='页面可访问；核验杭州智能回收箱操作、投放规模、分类准确率、月回收量和后端分类事实。'
  5='页面可访问；核验2024年回收体系指导意见的3R框架、2025年三项数量目标和2030年系统目标。'
}
foreach($x in ($sample|Where-Object topic -eq '环境')){
  $n=[int](($x.source_url -split '/')[-2] -eq 'c.html')
  $sid = switch($x.difficulty){1{'src-环境-01'}2{'src-环境-02'}3{'src-环境-03'}4{'src-环境-04'}5{'src-环境-05'}}
  $num=[int]($sid.Substring($sid.Length-2)); $x.corpus_id="cet-human-environment-l$($x.difficulty)-$('{0:D2}' -f $num)"; $x|Add-Member source_id $sid -Force; $x|Add-Member source_verification $verify[[int]$x.difficulty] -Force
  foreach($q in $x.questions){ $q.options = @($q.options) }
  if([int]$x.difficulty -eq 1){
    ($x.questions | Where-Object type -eq 'word_guess').question = 'In context, which meaning fits levers?'
    ($x.questions | Where-Object type -eq 'attitude').question = 'Which evaluation of one climate project matches the writer?'
  }
  $items.Add($x)
}

$c = @'
Chongqing has been trying to make zero waste a direction for city management rather than a literal promise that no rubbish will exist. In one industrial example, residues that once had disposal costs can be examined, separated and offered as inputs to another producer. The city has also expanded household sorting and treatment capacity.

The phrase matters because a slogan can set the wrong expectation. A growing city will still produce discarded material. The practical task is to prevent avoidable waste, keep hazardous items out of ordinary bins and recover useful resources at a reliable quality. These jobs belong to different actors, from residents and collectors to factories and regulators.

Coordination is therefore more important than a perfect-looking final bin. If a factory changes its material but a recycler is not told, the recovered output may no longer meet a buyer's standard. If households sort carefully but collection vehicles mix the bags again, trust quickly disappears.

A zero-waste program should publish evidence: how much waste was prevented, safely treated, and where recovered material actually went. That information allows residents and firms to see whether separate actions form a working chain.

The useful meaning of zero waste is continuous reduction supported by traceable systems. It is a direction that makes each stage more responsible, not a claim that a modern city can make every unwanted object vanish.
'@
Add-Env 6 1 'Zero Waste Is a Direction, Not a Vanishing Act' $c '页面可访问；核验重庆推进无废城市建设、工业固废资源化和生活垃圾分类处理等报道事实；正文不把无废误写成绝对零垃圾。' 'A zero-waste city needs coordinated prevention, safe treatment and real reuse rather than a literal promise of no rubbish.' 'The useful meaning of zero waste is continuous reduction supported by traceable systems.' 'Why can carefully sorted household bags still fail to build trust?' 'Later collection may mix them again.' 'If households sort carefully but collection vehicles mix the bags again, trust quickly disappears.' 'traceable' 'possible to follow through recorded stages' 'That information allows residents and firms to see whether separate actions form a working chain.' 'Different actors must exchange information for recovered materials to remain useful.' 'These jobs belong to different actors, from residents and collectors to factories and regulators.' 'The writer is supportive of the goal but rejects an absolute reading of its slogan.' 'It is a direction that makes each stage more responsible, not a claim that a modern city can make every unwanted object vanish.'

$c=@'
A fleet of hydrogen-powered heavy trucks opened a long freight route across regions in April 2025. The route stretches about 1,150 kilometres and is supported by four hydrogen refuelling stations. It offers a practical test of whether low-carbon fuel can serve vehicles that carry heavy loads over long distances.

Distance alone is not the whole experiment. A truck must find fuel when its timetable requires it, not merely when a station happens to be open. Four stations therefore form a corridor: a connected line of service points that makes a journey possible. Reliability at any one point affects the entire route.

Hydrogen trucks also move the environmental question beyond the tailpipe. Their climate value depends partly on how the hydrogen is produced and transported. Fuel made with low-carbon electricity has a different footprint from fuel whose production depends heavily on fossil energy. Measuring only exhaust from the vehicle would hide this difference.

Operators can learn from freight records. Fuel use, waiting time, maintenance and load weight reveal whether the system works outside a demonstration. The route should be compared with realistic alternatives, including efficient rail or battery vehicles where those fit the task.

The 1,150-kilometre run is therefore evidence of infrastructure beginning to connect, not proof that one technology suits every journey. Its strongest contribution is the opportunity to measure a complete transport system under working conditions.
'@
Add-Env 7 1 'Four Stations Make a Hydrogen Corridor' $c '替换页面可访问；核验2025-04-14报道的跨区域氢能重卡线路，采用1150公里和4座加氢站两项明确事实。' 'A hydrogen freight route should be judged as a complete fuel-and-vehicle system under real operating conditions.' 'Its strongest contribution is the opportunity to measure a complete transport system under working conditions.' 'What two figures define the reported freight corridor?' 'About 1,150 kilometres and four refuelling stations.' 'The route stretches about 1,150 kilometres and is supported by four hydrogen refuelling stations.' 'corridor' 'a linked series of service points along a route' 'Four stations therefore form a corridor: a connected line of service points that makes a journey possible.' 'Tailpipe data alone cannot establish the routes full climate value.' 'Their climate value depends partly on how the hydrogen is produced and transported.' 'The author treats the opening as a useful test, not a universal verdict.' 'The 1,150-kilometre run is therefore evidence of infrastructure beginning to connect, not proof that one technology suits every journey.' 'https://english.news.cn/20250414/9cd05035256848689508ecb065880026/c.html' 'China launches first cross-region hydrogen heavy-duty truck route' '2025-04-14'

$c = @'
Beijing's household rubbish does not end its journey when a collection truck leaves a neighbourhood. At treatment sites, mixed flows are weighed and inspected before suitable material is recovered, organic matter is treated and the remaining waste is handled under controlled conditions. Some facilities also use heat from incineration to generate electricity.

Calling this process turning trash green can attract attention, yet the color change is not automatic. Burning waste may reduce landfill demand and recover energy, but plants still need emissions controls and careful handling of ash. Food waste can produce useful outputs only when contamination is limited. Recycling succeeds only if separated material has a buyer.

Residents influence later stages through a decision at home. Correct separation makes equipment safer and recovered streams cleaner. However, information must be simple enough to use: a rule that changes between buildings or is printed in technical language creates mistakes even among willing households.

The city therefore needs feedback in both directions. Operators should tell communities which errors cause the greatest trouble, while collection data can show where instructions or facilities are failing. Residents are not merely the first step in a hidden industrial process; they are partners whose actions change its efficiency.

A greener rubbish system is not one impressive plant. It is a visible relationship between household choices, dependable collection, controlled treatment and markets that keep recovered resources in use.
'@
Add-Env 8 1 'The Journey After Beijings Bin' $c '页面可访问；核验北京生活垃圾分类、收运、资源化处理和焚烧发电等报道事实；正文围绕前端分类与后端治理的连接原创改写。' 'Household sorting has value only when it connects with controlled treatment and usable markets.' 'It is a visible relationship between household choices, dependable collection, controlled treatment and markets that keep recovered resources in use.' 'Why do simple and stable sorting instructions matter?' 'Complex or changing rules can produce errors despite good intentions.' 'a rule that changes between buildings or is printed in technical language creates mistakes even among willing households.' 'contamination' 'unwanted material mixed into a recoverable stream' 'Food waste can produce useful outputs only when contamination is limited.' 'Treatment plants need feedback from communities as well as machinery.' 'The city therefore needs feedback in both directions.' 'The discussion is cautiously practical about both benefits and operating risks.' 'Burning waste may reduce landfill demand and recover energy, but plants still need emissions controls and careful handling of ash.'

$c=@'
A forest ranger in Hainan has watched damaged land recover as protection became more systematic. Patrols, habitat restoration and limits on harmful activity can gradually return shade, water retention and living space for wildlife. The visible return of vegetation is encouraging, but a forest is more than a count of trees.

Rangers provide continuity that short projects often lack. They notice an unusual sound, a blocked stream or a new path before these changes appear in an annual report. Local observation can guide specialists toward places that need closer measurement. It also helps explain protection rules to nearby communities.

Restoration is not the same as planting the largest possible number of seedlings. Species must fit soil, elevation and rainfall, while young growth needs time to develop varied layers. A single fast-growing species may make a hillside look green quickly but support fewer ecological relationships.

Long records are especially valuable because tropical systems change with seasons and storms. One photograph cannot show whether soil remains stable or wildlife continues to return. A ranger's repeated notes, combined with scientific surveys, turn separate moments into evidence of direction.

The story of one observer does not replace ecological data. It shows why protection needs people who remain close enough to see change developing. Forest recovery becomes credible when patient local knowledge and measured results correct and strengthen one another.
'@
Add-Env 9 1 'A Ranger Sees the Forest Between Surveys' $c '页面可访问；核验海南护林员长期见证生态修复的报道主线，采用巡护、植被恢复和生态保护等有限事实，未虚构具体物种数据。' 'Forest restoration is best understood through sustained local observation joined with scientific measurement.' 'Forest recovery becomes credible when patient local knowledge and measured results correct and strengthen one another.' 'Why can one green photograph mislead a restoration review?' 'It cannot show long-term soil stability or continuing wildlife return.' 'One photograph cannot show whether soil remains stable or wildlife continues to return.' 'continuity' 'attention maintained across time rather than a single visit' 'Rangers provide continuity that short projects often lack.' 'A rapid increase in tree cover may still represent a weak ecosystem.' 'A single fast-growing species may make a hillside look green quickly but support fewer ecological relationships.' 'The passage values rangers without presenting personal observation as sufficient alone.' 'The story of one observer does not replace ecological data.'

$c=@'
At Qilihai Wetland in northern China, managers reported a record bird count and noticed some migration arriving earlier than before. Such observations can signal that habitat protection is working. They can also raise a harder question: which changes belong to local management, and which reflect weather or wider climate patterns?

A record is a comparison with previous observations made under stated conditions. It is not automatically a permanent population increase. Counts can change with survey routes, timing, visibility and the length of a stop during migration. Good monitoring records these conditions instead of treating the largest number as a trophy.

Earlier arrival requires similar care. Birds may respond to temperature, food or conditions elsewhere on their route. Wetland staff can protect resting and feeding areas, but they do not control the entire journey. Sharing observations with other sites helps turn a local date into information about a moving population.

Public excitement still has value. Birdwatching can create support for quiet zones and habitat investment. Yet publicity should explain why visitors must keep distance during sensitive periods. More attention is useful only if it does not disturb the behavior being celebrated.

Qilihai's records therefore work best as questions with a history, not as isolated proof. Repeated methods, regional cooperation and careful access can convert an exciting season into knowledge that improves protection.
'@
Add-Env 10 2 'A Record Bird Count Is the Start of a Question' $c '页面可访问；核验七里海湿地创纪录鸟类数量和迁徙时间提前的报道事实；正文明确区分观测记录、可能原因与管理结论。' 'Wetland records become useful when consistent monitoring and regional context explain what changed.' 'Repeated methods, regional cooperation and careful access can convert an exciting season into knowledge that improves protection.' 'Which factors can alter a wetland bird count besides population size?' 'Survey route, timing, visibility and stopover length.' 'Counts can change with survey routes, timing, visibility and the length of a stop during migration.' 'record' 'a result compared with earlier observations under stated conditions' 'A record is a comparison with previous observations made under stated conditions.' 'Earlier migration cannot be attributed to the wetland alone.' 'Birds may respond to temperature, food or conditions elsewhere on their route.' 'The writer welcomes public interest only when it respects sensitive wildlife.' 'More attention is useful only if it does not disturb the behavior being celebrated.'

$c=@'
China announced a stronger push on solid-waste management in 2026. The task covers far more than household bins. Industrial residues, construction material, agricultural waste, obsolete products and hazardous substances follow different routes, carry different risks and often involve separate regulators.

This variety explains why one national tonnage can conceal weak links. A large amount of metal may be recovered successfully while a smaller hazardous stream is handled poorly. Good management must identify material before choosing transport, storage or treatment. Traceability means that its origin and movement can be followed when something goes wrong.

Prevention deserves attention before treatment. A factory can redesign production to use fewer inputs; a building project can plan for reusable components; a retailer can make repair possible. These changes may create less visible material for a recycling report precisely because they stop waste from appearing.

The system also needs markets, but price cannot be the only signal. When recovered material loses value, unsafe dumping becomes more tempting. Standards, inspections and producer responsibility help keep environmental duties in place through market changes.

A broad campaign succeeds when it makes different waste streams legible and assigns responsibility across their full life. The goal is not simply to move piles away from public view. It is to prevent harm, preserve useful value and leave an accountable record from origin to final use.
'@
Add-Env 11 2 'Solid Waste Is Many Systems, Not One Pile' $c '页面可访问；核验2026年加强固体废物综合治理的报道主线及工业、建筑、农业、生活和危险废物等治理范围。' 'Solid-waste policy must distinguish material streams and keep responsibility visible across their entire life.' 'A broad campaign succeeds when it makes different waste streams legible and assigns responsibility across their full life.' 'Why can a single recovery tonnage hide a serious weakness?' 'Success with a large stream can mask poor handling of a smaller hazardous one.' 'A large amount of metal may be recovered successfully while a smaller hazardous stream is handled poorly.' 'traceability' 'the ability to follow origin and movement through records' 'Traceability means that its origin and movement can be followed when something goes wrong.' 'Waste prevention may lower reported recycling volumes for a beneficial reason.' 'These changes may create less visible material for a recycling report precisely because they stop waste from appearing.' 'The author sees markets as useful but insufficient safeguards.' 'The system also needs markets, but price cannot be the only signal.'

$c=@'
China's recycling sector has been described as a possible source of new economic growth. Used metal, appliances, vehicles and other products can support collection firms, testing services, repair work and manufacturing based on recovered inputs. This activity can reduce demand for newly extracted resources while creating jobs.

Growth, however, should not be confused with rapid turnover alone. A second-hand appliance that works safely may deliver more service with little processing. If it is broken too early merely to increase recycling volume, energy and usable value are lost. The preferred route depends on condition, safety and the environmental cost of each option.

Quality information makes these choices possible. Sellers need clear grading, buyers need reliable tests, and processors need standards for recovered material. Without them, good products may be priced like waste and poor material may enter production with hidden risks.

Digital platforms can connect supply and demand, but they also create duties. Personal data must be removed from phones and computers; prices and responsibility for defects should be understandable. Trust is an economic input because uncertain transactions often do not happen.

The sector's strongest growth comes from extending useful life and returning dependable material to production. Revenue is evidence of activity, not a complete environmental score. A mature circular market earns value by making the safer and less wasteful choice easier to recognize.
'@
Add-Env 12 2 'When Recycling Growth Preserves Usefulness' $c '页面可访问；核验报道关于再生资源回收利用、二手流通、设备更新和循环经济增长空间的事实主线。' 'A recycling economy creates durable value when it preserves product use and verifies recovered material quality.' 'A mature circular market earns value by making the safer and less wasteful choice easier to recognize.' 'What information do buyers need before accepting a used appliance?' 'Reliable testing and clear grading of its condition.' 'Sellers need clear grading, buyers need reliable tests, and processors need standards for recovered material.' 'turnover' 'the speed or amount of goods moving through transactions' 'Growth, however, should not be confused with rapid turnover alone.' 'Breaking a usable product for recycling can reduce environmental value.' 'If it is broken too early merely to increase recycling volume, energy and usable value are lost.' 'The author treats revenue as informative but incomplete.' 'Revenue is evidence of activity, not a complete environmental score.'

$c=@'
A nationwide carbon plan may use targets, standards and projects, but people meet it through ordinary systems. Transport schedules influence whether a commuter drives. Building design affects energy use for decades. Product repair rules determine whether an object remains useful. Electricity markets shape when cleaner power can enter the grid.

This is why climate policy cannot rely on a single dramatic technology. Emissions come from connected decisions made by households, firms and public agencies. A national framework can set direction, while sectors and regions need routes suited to their resources and responsibilities.

Coordination does not mean every place follows an identical timetable. It means one decision should not quietly cancel another. Expanding renewable power, for example, brings limited benefit if grids cannot transmit it or demand cannot respond when output changes. Industrial efficiency gains may also be weakened if total material demand rises faster.

Progress needs both outcome measures and transition safeguards. Carbon intensity can fall while total emissions remain high; a new industry can grow while workers in an older one need retraining. Reporting these tensions does not weaken commitment. It makes implementation more credible.

Climate action becomes durable when rules, infrastructure and daily choices point in the same direction. The central achievement of a plan is therefore not the number of policies it lists, but whether their incentives continue to align as conditions change.
'@
Add-Env 13 2 'A Climate Plan Must Align Everyday Systems' $c '页面可访问；核验白皮书关于双碳政策框架、能源转型、重点领域降碳、循环经济、碳汇和保障体系等公开内容。' 'Durable climate action requires policies and everyday systems to keep their incentives aligned.' 'Climate action becomes durable when rules, infrastructure and daily choices point in the same direction.' 'Why is extra grid capacity relevant when renewable generation expands?' 'Clean electricity needs transmission and flexible demand to be used effectively.' 'Expanding renewable power, for example, brings limited benefit if grids cannot transmit it or demand cannot respond when output changes.' 'coordination' 'preventing connected actions from undermining one another' 'It means one decision should not quietly cancel another.' 'Transparent discussion of transition tensions can strengthen implementation.' 'Reporting these tensions does not weaken commitment. It makes implementation more credible.' 'The author favors a shared national direction with locally suitable routes.' 'A national framework can set direction, while sectors and regions need routes suited to their resources and responsibilities.'

$c=@'
The Taklimakan Desert covers about 337,600 square kilometres. Around its edge, people have worked for decades to slow the movement of sand through forests, grass barriers, solar projects and other methods suited to different ground. On November 28, 2024, the final gap in a 3,046-kilometre green belt around the desert was closed.

The word closed describes a geographic connection, not the end of desertification control. Young plants still face drought, wind and shifting sand. Water is scarce, so survival matters more than the number planted on opening day. Monitoring must identify where shelter belts weaken and which species remain suitable as conditions change.

The belt is also not a solid wall. Its ecological function depends on a mosaic of vegetation and engineered barriers that reduce wind near roads, farms and settlements. In some places, photovoltaic panels can lower surface wind while generating electricity, but their construction and cleaning must fit local water and habitat limits.

Local livelihoods influence maintenance. If protection creates stable work, useful forest products or safer transport, communities have practical reasons to care for it. Projects that ignore grazing routes or water needs may transfer pressure rather than remove it.

Scale can inspire confidence, yet it should sharpen evaluation. Managers need to compare plant survival, sand movement, water use and effects on nearby land over many years. The green belt's completion is a milestone because separated projects now form a continuous protective system. Its lasting success will be measured by whether that system remains alive, adaptive and affordable in an extremely dry landscape.
'@
Add-Env 14 3 'Closing a Desert Belt Opens a Maintenance Test' $c '替换页面可访问；核验塔克拉玛干沙漠约337600平方公里、3046公里防护带以及2024-11-28锁边合龙三项事实。' 'Completing the desert belt begins a long test of ecological maintenance rather than ending control work.' 'Its lasting success will be measured by whether that system remains alive, adaptive and affordable in an extremely dry landscape.' 'Which date marked closure of the last gap around the desert?' 'November 28, 2024.' 'On November 28, 2024, the final gap in a 3,046-kilometre green belt around the desert was closed.' 'mosaic' 'a system made from different elements arranged together' 'Its ecological function depends on a mosaic of vegetation and engineered barriers' 'Water-efficient survival is more meaningful than planting-day totals.' 'Water is scarce, so survival matters more than the number planted on opening day.' 'The author regards the connected belt as a milestone whose performance still needs years of evidence.' 'The green belt''s completion is a milestone because separated projects now form a continuous protective system.' 'https://english.news.cn/20250414/7814f13c678f420b886b0ef78a81795b/c.html' 'EcoChina | Sand control, afforestation efforts in China''s largest desert' '2025-04-14'

$c=@'
China reported that carbon dioxide emissions per 10,000 yuan of gross domestic product fell by 5 percent in 2025. The indicator links emissions with economic output and is often called carbon intensity. A decline means the economy produced each measured unit of value with less carbon than before.

That is useful information, but it does not answer every climate question. Total emissions can still rise if output grows faster than intensity falls. Conversely, a temporary economic slowdown may improve a ratio without demonstrating structural change. The numerator and denominator must therefore be examined separately.

Sector detail adds meaning. Efficiency in steel production, cleaner electricity, better buildings and a shift toward services can all lower intensity, but they require different policies. Imports also complicate interpretation: domestic statistics may improve if carbon-intensive production moves elsewhere, even though consumption continues.

An intensity measure is valuable for comparing efficiency over time while allowing for economic growth. Its limitation is not a reason to discard it. Instead, policymakers can place it beside absolute emissions, energy mix, investment and household impacts. Together these indicators show whether progress is broad or dependent on one temporary change.

Communication should preserve this distinction. Saying that the economy became less carbon-intensive is accurate; saying that emissions necessarily fell by the same percentage is not. The 5-percent result is best understood as one coordinate on a larger map of transition.

Good climate accounting makes each measure do the job it was designed to do. It resists both dismissing a real efficiency gain and stretching that gain into a conclusion the ratio cannot support.
'@
Add-Env 15 3 'What a Five-Percent Carbon-Intensity Fall Means' $c '页面可访问；核验2025年单位GDP二氧化碳排放下降5%的报道数据，并按指标定义限定其含义。' 'Carbon intensity is informative only when its efficiency signal is distinguished from total emissions.' 'Good climate accounting makes each measure do the job it was designed to do.' 'What exactly declined by five percent in the report?' 'Carbon dioxide emissions per 10,000 yuan of GDP.' 'China reported that carbon dioxide emissions per 10,000 yuan of gross domestic product fell by 5 percent in 2025.' 'intensity' 'emissions measured relative to a unit of economic output' 'The indicator links emissions with economic output and is often called carbon intensity.' 'Economic growth can cause total emissions to rise despite a lower ratio.' 'Total emissions can still rise if output grows faster than intensity falls.' 'The writer accepts the indicator while insisting on companion measures.' 'Its limitation is not a reason to discard it.'

$c=@'
A 2025 white paper described changes in China's energy system: rapid growth in wind and solar capacity, wider electrification, stronger grids, storage and efficiency work. These parts are sometimes presented as separate achievements. In practice, their value depends on how they interact.

Variable renewable generation is a clear example. A solar plant produces power when light is available, not simply when demand peaks. Transmission can move electricity across regions, storage can shift some supply through time, and flexible users can adjust consumption. None is a complete substitute for the others.

The transition also follows the principle of establishing new capacity before retiring old supply. This sequencing aims to protect energy security while cleaner systems become dependable. It can prevent shortages, but it also requires transparent tests for when old assets are no longer needed. Without such tests, temporary backup may persist and slow emissions reduction.

Technology choices carry local consequences. A large renewable base uses land and transmission corridors; hydropower changes rivers; batteries require minerals and later recycling. Calling an energy source low-carbon does not remove the need to compare siting, materials and ecological effects.

Progress should therefore be evaluated as system performance. Relevant evidence includes not only installed capacity but also electricity actually delivered, curtailment, reliability, cost and lifecycle impact. A transition advances when new equipment changes how the whole network operates.

The white paper's broad inventory is most meaningful when read as an argument for connection. Energy security and decarbonization are not competing scoreboards; good sequencing and accountable infrastructure must allow them to improve together.
'@
Add-Env 16 3 'An Energy Transition Is a Networked Achievement' $c '页面可访问；核验白皮书关于风光装机、电网互济、储能、需求响应和先立后破等能源转型内容。' 'Energy transition should be measured by connected system performance, not isolated equipment totals.' 'Progress should therefore be evaluated as system performance.' 'Why are transmission and storage discussed together with solar power?' 'They help move variable electricity across space and time.' 'Transmission can move electricity across regions, storage can shift some supply through time, and flexible users can adjust consumption.' 'sequencing' 'ordering changes so new capacity becomes reliable before old supply retires' 'This sequencing aims to protect energy security while cleaner systems become dependable.' 'Backup assets need transparent retirement tests or they may become permanent.' 'Without such tests, temporary backup may persist and slow emissions reduction.' 'The evaluation is supportive of low-carbon growth but attentive to lifecycle and local effects.' 'Calling an energy source low-carbon does not remove the need to compare siting, materials and ecological effects.'

$c=@'
Reports on China's 2021–2025 energy transition point to rapid renewable expansion and a changing relationship among production, networks and consumption. A five-year view is useful because major power projects take time. It is also dangerous if the beginning and end are chosen to tell only a smooth story.

Installed capacity measures how much equipment could generate under stated conditions. Actual generation depends on weather, grid access, maintenance and demand. A capacity record may therefore coexist with curtailment, while a smaller flexible resource can contribute greatly during a difficult hour.

Electrification shifts vehicles, heating or industry from direct fuel use toward power. Its climate effect improves as electricity becomes cleaner. This creates a moving relationship: progress on the demand side increases the importance of grid decarbonization, and clean generation gains value when more end uses can take it.

Five-year evaluation should examine distribution as well as totals. Regions supply different resources and face different costs. Workers and communities tied to older energy industries may need retraining, fiscal support and time. A national gain can still contain concentrated local burdens.

Uncertainty also belongs in planning. Weather, technology prices and demand can change faster than construction schedules. Scenario analysis tests whether a strategy remains workable under several plausible futures rather than predicting one path with false precision.

The strongest account of transition is neither a celebration of capacity nor a list of obstacles. It shows how physical investment, market rules and social adjustment changed together—and where their speeds still fail to match.
'@
Add-Env 17 3 'Five Years of Energy Change Need More Than Endpoints' $c '页面可访问；核验2021至2025年绿色低碳能源转型、可再生能源扩张、电气化和电力系统建设等报道主线。' 'A five-year energy assessment must connect physical, market and social change rather than compare endpoints alone.' 'It shows how physical investment, market rules and social adjustment changed together—and where their speeds still fail to match.' 'What limits the electricity produced from installed capacity?' 'Weather, grid access, maintenance and demand.' 'Actual generation depends on weather, grid access, maintenance and demand.' 'scenario analysis' 'testing a strategy across several plausible future conditions' 'Scenario analysis tests whether a strategy remains workable under several plausible futures rather than predicting one path with false precision.' 'Electrifying demand has greater climate value as the power supply becomes cleaner.' 'Its climate effect improves as electricity becomes cleaner.' 'The author balances evidence of expansion with questions about distribution and timing.' 'A national gain can still contain concentrated local burdens.'

$c=@'
A report stated that renewable sources met all growth in China's electricity demand in 2025. The sentence sounds simple, but it describes a change at the margin: compared with the previous period, the additional demand was matched by additional renewable generation. It does not say that every unit of electricity came from renewables.

Marginal change matters because it shows whether a power system is moving toward cleaner supply while consumption expands. If renewable output grows faster than demand, fossil generation may decline. If demand later accelerates or renewable conditions weaken, the relationship can reverse. One year is evidence, not a permanent law.

The composition of demand also affects interpretation. New electricity use may replace petrol in vehicles or coal in heating, producing emissions benefits beyond the power sector. Alternatively, rapid growth from inefficient equipment can increase pressure on networks. Analysts need to ask what electricity is doing, not merely how much was consumed.

Grid constraints determine whether available clean power reaches users. Transmission, storage, flexible demand and market dispatch can reduce curtailment. These supporting systems may be less visible than a new wind farm, yet they decide how much renewable output becomes useful supply.

The report's finding is encouraging precisely because it concerns a dynamic balance. The next test is whether clean generation can continue covering growth while reliability improves and older high-emission production is displaced rather than simply held in reserve.

Careful language protects the value of the result. Met the increase is a significant systems claim; turning it into supplied all electricity would replace progress with exaggeration. Precision also lets later reports test whether the same balance persists under different weather and demand.
'@
Add-Env 18 4 'All New Demand Is Not All Electricity' $c '页面可访问；核验报告关于2025年可再生能源满足中国全部新增电力需求的结论，并严格区分增量与总量。' 'The renewable-demand finding is significant only when its marginal meaning is stated accurately.' 'Met the increase is a significant systems claim; turning it into supplied all electricity would replace progress with exaggeration.' 'What does met all growth describe in this report?' 'Additional renewable generation matched the increase in electricity demand.' 'the additional demand was matched by additional renewable generation.' 'at the margin' 'concerning the added amount rather than the entire total' 'it describes a change at the margin' 'Grid support determines whether potential renewable output becomes usable supply.' 'These supporting systems may be less visible than a new wind farm, yet they decide how much renewable output becomes useful supply.' 'The author considers the result encouraging but explicitly time-bound.' 'One year is evidence, not a permanent law.'

$c=@'
China's 2025 environmental report described improvement across air, surface water and ecological protection. A national summary is useful for accountability, but each average compresses geography, seasons and pollutants. Two places can move in opposite directions while the combined number improves.

Air quality illustrates the problem. The share of days meeting a standard tells residents how often conditions were acceptable, while annual particle concentration describes average exposure. Neither shows every short severe episode. Water indicators likewise depend on which sections are monitored, when samples are taken and which substances are tested.

This does not make national statistics untrustworthy. It means the measurement design must be visible. Stable monitoring sites allow comparison through time; added sites can improve coverage but may change the national average even before the environment changes. Publishing methods helps readers separate ecological movement from statistical movement.

Cross-media analysis is also important. A factory that reduces air emissions by transferring pollution into wastewater has not created a complete gain. Policies should follow materials through treatment rather than reward improvement in one column alone. Ecological indicators, such as habitat condition or species trends, add information that chemical concentrations cannot capture.

Public communication can offer layers: a national direction, regional maps, local station data and explanations of unusual events. This structure avoids forcing one number to serve experts, officials and residents equally.

Improvement is most credible when people can examine where it occurred, how it was measured and which problems remain. Local comparisons can then reveal whether national gains reach communities facing the heaviest exposure. Comparable local series can expose uneven progress. A summary should open the evidence rather than close the discussion.
'@
Add-Env 19 4 'An Environmental Average Needs a Map Behind It' $c '页面可访问；核验2025年全国生态环境质量改善及空气、地表水等指标的报道主线；正文不新增未经来源支持的具体比例。' 'National environmental improvement becomes credible when methods and geographic detail remain visible.' 'Comparable local series can expose uneven progress. A summary should open the evidence rather than close the discussion.' 'Why might adding monitoring sites change an average?' 'New coverage can alter the measured sample even before conditions change.' 'added sites can improve coverage but may change the national average even before the environment changes.' 'compresses' 'combines varied places and times into a smaller summary' 'each average compresses geography, seasons and pollutants.' 'A cleaner air column can conceal pollution shifted into water.' 'A factory that reduces air emissions by transferring pollution into wastewater has not created a complete gain.' 'The author accepts national indicators while demanding transparent layers beneath them.' 'This does not make national statistics untrustworthy.'

$c=@'
A study linked rising solar radiation over parts of China with cleaner air. When concentrations of certain airborne particles fall, less sunlight is scattered or blocked before reaching the ground. Long records of surface radiation can therefore carry information about changes in pollution control.

The connection is scientifically useful because it combines two kinds of observation. Air monitors measure pollutants directly, while radiation records show an effect of the atmosphere. Agreement between independent datasets strengthens an explanation. Disagreement can reveal changes in clouds, humidity, instruments or particle composition that need investigation.

More sunlight at the surface is not a simple measure of environmental benefit. Stronger radiation can raise solar-power output, but it may also increase heat stress or ultraviolet exposure under some conditions. Cleaner air remains valuable for health regardless of whether every consequence of added sunlight is positive.

Causation also needs careful design. Radiation changes with cloud cover, water vapor and seasonal circulation. Researchers must control for these influences before attributing a trend to aerosol reduction. A correlation is most persuasive when physical mechanisms and multiple observations point in the same direction.

The finding illustrates how environmental policies create signals beyond the pollutant named in a regulation. Better air can alter visibility, surface energy and renewable generation. These secondary effects should be measured without being advertised as guaranteed everywhere.

The study's strongest lesson is methodological: environmental progress can become clearer when scientists connect records that were originally collected for different purposes. Careful replication across regions should test whether the same mechanisms hold under different climates. The resulting picture is richer than either dataset alone, provided uncertainty stays visible.
'@
Add-Env 20 4 'Sunlight Can Carry a Record of Cleaner Air' $c '页面可访问；核验研究关于中国地表太阳辐射上升与空气污染治理、气溶胶下降关联的报道结论。' 'Independent radiation and air-quality records can jointly strengthen evidence of pollution change.' 'Careful replication across regions should test whether the same mechanisms hold under different climates. The resulting picture is richer than either dataset alone, provided uncertainty stays visible.' 'What atmospheric change can let more sunlight reach the surface?' 'A reduction in particles that scatter or block radiation.' 'When concentrations of certain airborne particles fall, less sunlight is scattered or blocked before reaching the ground.' 'mechanisms' 'physical processes that explain how one change produces another' 'A correlation is most persuasive when physical mechanisms and multiple observations point in the same direction.' 'Increased surface radiation has effects beyond solar generation.' 'it may also increase heat stress or ultraviolet exposure under some conditions.' 'The writer finds the result valuable but refuses to treat correlation as sufficient by itself.' 'Researchers must control for these influences before attributing a trend to aerosol reduction.'

$c=@'
National political meetings can place climate action beside economic targets, industrial policy and public welfare. This proximity matters. Climate goals are easiest to postpone when they are treated as a separate environmental chapter rather than as constraints and opportunities inside everyday development decisions.

Investment choices demonstrate the connection. Funding a factory, transport line or building creates patterns of energy and material use that may last for decades. A project that appears cheap this year can become costly if future carbon rules, extreme weather or fuel prices are ignored. Long-lived assets need transition risk considered before construction.

Policy momentum is more than frequent speech. It requires budgets, standards, enforcement and institutions able to coordinate. National direction can reduce uncertainty for firms, yet local implementation determines whether permits, grids and training arrive on time. Too many changing signals may delay investment even when the headline goal remains stable.

International effects add another layer. Large markets can lower the cost of clean technologies through scale, while demand for minerals and equipment reshapes supply chains. Climate contributions should therefore be judged through both domestic outcomes and the conditions under which products are made and traded.

Public welfare is not an obstacle external to transition. Cleaner air, resilient infrastructure and new employment can create benefits, while poorly designed changes can raise household costs or concentrate losses in particular regions. Fairness affects political durability.

The meetings add momentum when they convert broad direction into decisions that survive annual cycles. Published milestones and later review can show whether announced priorities retained funding and enforcement after the meetings ended. Climate policy becomes credible where economic planning repeatedly prices long-term environmental consequences into present choices.
'@
Add-Env 21 4 'Climate Momentum Must Enter Ordinary Decisions' $c '页面可访问；核验2025年全国两会关于绿色转型、气候行动、产业发展和国际合作的报道主线。' 'Climate commitments gain durability when economic planning incorporates their long-term consequences.' 'Climate policy becomes credible where economic planning repeatedly prices long-term environmental consequences into present choices.' 'Why do construction and factory decisions deserve early climate review?' 'They lock in energy and material patterns for decades.' 'Funding a factory, transport line or building creates patterns of energy and material use that may last for decades.' 'momentum' 'continued movement produced by institutions and concrete decisions' 'Policy momentum is more than frequent speech.' 'Fair distribution can affect whether climate policy lasts politically.' 'Fairness affects political durability.' 'The author treats national meetings as useful only when direction becomes budgets, standards and implementation.' 'It requires budgets, standards, enforcement and institutions able to coordinate.'

$c=@'
Renewable energy in China has moved from a supplementary role toward a central place in new power investment. Large wind and solar bases, distributed rooftop systems and offshore projects expand supply under very different geographic conditions. Their speed attracts attention, yet acceleration changes the problem policymakers must solve.

When capacity is scarce, the priority is usually construction. When variable generation becomes abundant, the harder task is integration. Grid operators must forecast output, move electricity between regions and reward flexible demand. Storage can shift some energy, but technologies differ in duration, cost, materials and suitable location. Treating all storage as interchangeable would repeat the mistake of counting renewable capacity without asking when it serves demand.

Fast growth also makes siting decisions consequential. Desert projects may use land with low agricultural value, but roads and transmission lines can still affect habitats. Distributed solar reduces long-distance needs yet depends on safe roofs, fair contracts and local network upgrades. Offshore wind brings strong resources alongside marine construction and maintenance risks. Renewable identifies an energy flow; it does not decide the responsible design of every project.

Manufacturing scale can lower global technology costs. It can also concentrate demand for minerals, water and industrial energy. Lifecycle rules should encourage durable equipment, repairable components and recovery of metals when panels, turbines or batteries retire. Otherwise, today's clean infrastructure creates tomorrow's poorly planned waste stream.

Markets must change with engineering. Prices that ignore congestion can encourage power where the grid cannot accept it. Long-term contracts can reduce investment risk, while transparent curtailment data reveal where network expansion or flexible demand has greater value than another generator.

The fast lane is therefore not a straight road measured only in gigawatts. Renewable expansion becomes a transition when generation, networks, demand, land governance and material recovery advance together. The next stage should reward useful clean electricity and responsible assets, not construction detached from system need.
'@
Add-Env 22 5 'The Renewable Fast Lane Has Junctions' $c '页面可访问；核验可再生能源装机快速增长、集中式与分布式建设以及电网消纳等报道事实主线。' 'Rapid renewable construction becomes a true transition only through integration, responsible siting and lifecycle planning.' 'Renewable expansion becomes a transition when generation, networks, demand, land governance and material recovery advance together.' 'What becomes the harder task after variable capacity grows abundant?' 'Integrating output with grids, storage and flexible demand.' 'When variable generation becomes abundant, the harder task is integration.' 'curtailment' 'available generation reduced because the system cannot accept it' 'transparent curtailment data reveal where network expansion or flexible demand has greater value than another generator.' 'Distributed solar may reduce transmission needs while creating local contract and network duties.' 'Distributed solar reduces long-distance needs yet depends on safe roofs, fair contracts and local network upgrades.' 'A renewable label does not settle the environmental design of a project.' 'Renewable identifies an energy flow; it does not decide the responsible design of every project.'

$c=@'
A broad account of China's green transition combines several narratives: renewable manufacturing, cleaner transport, ecosystem restoration, pollution control and international cooperation. Placed together, they suggest that environmental policy can produce industrial and social change rather than merely restrict activity. The breadth is valuable, but it creates a risk of adding unlike achievements into one undefined success.

Different indicators answer different questions. Installed clean-energy capacity describes infrastructure; avoided emissions require a counterfactual about what would otherwise have happened. Forest area does not automatically reveal ecological quality. Exports of low-carbon equipment may reduce costs abroad, yet their benefit depends on use, displacement and manufacturing conditions. A credible synthesis must preserve these distinctions.

Scale can create spillovers. Larger production may improve technical learning and reduce prices, allowing other countries to adopt equipment sooner. It can also intensify competition or dependence in supply chains. International climate contribution is therefore not measured by export volume alone. Product durability, finance, local skills, recycling arrangements and fair access shape whether equipment supports lasting change.

Domestic coordination poses a similar challenge. Cleaner electricity strengthens the case for electric transport; better grids increase the value of remote wind and solar; restored ecosystems can improve resilience around settlements. These links produce benefits that isolated statistics miss. They also transmit weakness: a congested grid can limit several sectors at once.

The phrase clean, beautiful world is normative, expressing a desired direction rather than a completed scientific result. Evaluation should ask who benefits, which harms decline, what new pressures appear and how uncertainty is reported. Shared aspiration becomes useful when it guides comparable evidence and mutual accountability.

A green transition is convincing not because every positive number can be placed under one heading, but because the relationships among them can be tested. The strongest global contribution joins lower-cost solutions with transparent impacts, local capacity and cooperation that leaves partners able to maintain what they adopt.
'@
Add-Env 23 5 'A Green Contribution Cannot Be One Grand Total' $c '页面可访问；核验报道关于中国加快绿色转型、清洁能源产业、生态保护及全球绿色合作的综合事实框架。' 'A broad green-transition claim remains credible only when unlike indicators and international effects are assessed distinctly.' 'A green transition is convincing not because every positive number can be placed under one heading, but because the relationships among them can be tested.' 'Why is installed capacity not identical to avoided emissions?' 'Avoidance requires evidence about the generation or activity displaced.' 'avoided emissions require a counterfactual about what would otherwise have happened.' 'normative' 'expressing a desired value or direction rather than a measured completion' 'The phrase clean, beautiful world is normative, expressing a desired direction rather than a completed scientific result.' 'Low-cost exported equipment contributes more when partners can operate and maintain it.' 'local skills, recycling arrangements and fair access shape whether equipment supports lasting change.' 'The author supports cooperation while rejecting export volume as a sufficient score.' 'International climate contribution is therefore not measured by export volume alone.'

$c=@'
Next-generation low-carbon innovation is often described through striking devices: advanced batteries, green hydrogen equipment, carbon-capture systems or industrial processes powered by cleaner electricity. Demonstration projects matter because laboratory performance does not reveal how a technology behaves within weather, maintenance, regulation and real production schedules.

A demonstration has at least three jobs. It tests technical reliability, discovers operating costs and exposes institutional barriers. These jobs should be separated in reporting. A machine may work physically while remaining too expensive under current conditions; a financially attractive project may depend on rules that cannot easily scale. Calling both outcomes simply successful prevents learning.

Comparison with alternatives is essential. Carbon capture at an industrial site should be evaluated against efficiency, material substitution or process redesign, not against doing nothing. Hydrogen may be valuable for some high-temperature or heavy-transport uses while direct electrification is more efficient elsewhere. The relevant question is which tool addresses a hard-to-reduce source with the least total harm.

Innovation policy also creates a portfolio problem. Governments need enough variety to learn, but support can become locked into projects with strong sponsors and weak evidence. Stage gates can release additional funding only after safety, performance and environmental conditions are met. Independent publication of negative results reduces repeated mistakes.

Lifecycle accounting prevents a clean label from hiding upstream burdens. Energy source, material extraction, construction emissions, water demand, leakage and end-of-life treatment may alter the ranking of technologies. Boundaries should be wide enough to capture meaningful displacement without becoming impossible to measure.

Bold climate goals justify experimentation, not lower standards of proof. The most useful pilot is not necessarily the one that expands. It may reveal that a technology fits only a narrow role or that another approach performs better. Innovation advances when policy rewards reliable knowledge about where a tool belongs, including knowledge that limits its market.
'@
Add-Env 24 5 'A Climate Pilot Can Succeed by Staying Small' $c '页面可访问；核验报道关于新一代低碳技术、示范应用、绿色氢能及工业降碳创新的事实主线。' 'Low-carbon pilots should produce comparative, lifecycle evidence about where technologies fit, not merely justify expansion.' 'Innovation advances when policy rewards reliable knowledge about where a tool belongs, including knowledge that limits its market.' 'Which three functions should a demonstration report separately?' 'Technical reliability, operating cost and institutional barriers.' 'It tests technical reliability, discovers operating costs and exposes institutional barriers.' 'portfolio' 'a deliberately varied group of projects managed together under uncertainty' 'Innovation policy also creates a portfolio problem.' 'A technically working machine may still be an unsuitable large-scale choice.' 'A machine may work physically while remaining too expensive under current conditions' 'The author favors ambitious experiments under demanding evidence standards.' 'Bold climate goals justify experimentation, not lower standards of proof.'

$c=@'
Hainan's tropical rainforest illustrates conservation as a living system rather than a fenced collection of scenery. Protection involves habitat for wildlife, water regulation, carbon storage and communities whose histories and livelihoods are connected with the landscape. A national park can coordinate these interests across boundaries that individual reserves once managed separately.

Larger governance does not remove local variation. Elevation, rainfall and earlier disturbance create different restoration needs. Core habitat may require strict limits on access, while some surrounding areas can support research, education or carefully designed livelihoods. Zoning is not merely drawing colored lines; each boundary needs ecological evidence, enforceable rules and routes for adjustment.

Connectivity is especially important for species that move. A large total area can still contain isolated patches divided by roads or settlements. Wildlife corridors must be assessed by actual movement and survival, not only by their width on a map. Infrastructure planning should avoid new fragmentation before expensive repair becomes necessary.

Community participation is sometimes presented as consultation after a plan is complete. Meaningful participation begins earlier, when residents help identify seasonal use, conflict and feasible alternatives. Compensation alone may not replace access to land, cultural sites or familiar work. New opportunities in monitoring, ecological products or guiding need stable demand and fair distribution.

Tourism creates both support and pressure. Visitor limits, routes and waste systems should respond to habitat sensitivity rather than marketing targets. Revenue can help conservation, but only if financial flows and ecological costs are reported together.

The rainforest brings conservation efforts to life because relationships become visible: upstream forest affects downstream water, one road changes movement, and one rule changes a household's options. Long records must also reveal whether protection shifts pressure beyond park boundaries. Success lies in institutional capacity to notice these connections and revise action before damage becomes irreversible.
'@
Add-Env 25 5 'A Rainforest Park Governs Relationships' $c '页面可访问；核验海南热带雨林国家公园的生态保护、栖息地连通、社区参与和生态价值等报道主线。' 'Rainforest conservation depends on governing ecological and social relationships across a connected landscape.' 'Long records must also reveal whether protection shifts pressure beyond park boundaries. Success lies in institutional capacity to notice these connections and revise action before damage becomes irreversible.' 'Why can a large protected area still fail mobile wildlife?' 'Roads or settlements may isolate habitat patches inside it.' 'A large total area can still contain isolated patches divided by roads or settlements.' 'zoning' 'assigning areas different rules based on evidence and intended functions' 'Zoning is not merely drawing colored lines; each boundary needs ecological evidence, enforceable rules and routes for adjustment.' 'Consultation is stronger when communities shape alternatives before plans are fixed.' 'Meaningful participation begins earlier, when residents help identify seasonal use, conflict and feasible alternatives.' 'The writer accepts tourism only under ecological limits and transparent accounting.' 'Revenue can help conservation, but only if financial flows and ecological costs are reported together.'

$c=@'
Official data for the first seven months of 2026 indicated improvement in China's air and water quality. A partial-year result can provide an early signal, yet it is especially sensitive to seasonal composition. Seven months include particular heating patterns, rainfall, dust events and industrial schedules; the missing months may have systematically different conditions.

Year-on-year comparison reduces part of this problem by matching the same calendar period. It does not eliminate weather. Favorable winds can disperse pollution, while heavy rain can dilute some concentrations and wash other pollutants into rivers. Analysts use meteorological adjustment and multi-year context to distinguish policy effects from natural variability, though adjustment itself carries assumptions.

Air and water indicators also have different spatial logic. Air masses cross city borders quickly, so regional coordination may matter more than local emissions alone. A river connects upstream discharge, land runoff and downstream treatment. Improvement at a downstream station could reflect real source control, changed flow or pollution retained elsewhere. Monitoring networks must therefore be designed around movement, not administrative convenience.

Compliance rates summarize whether observations meet standards, but a threshold creates discontinuity. A small change can move one reading from not meeting to meeting without representing a dramatic ecological shift. Conversely, a large reduction that remains just above the line disappears from the compliance total. Concentration distributions should accompany pass rates.

Public reporting gains authority by showing revisions, missing observations and uncertainty. These details do not make the result less useful; they prevent an early signal from being mistaken for a final annual judgment. Local residents also need station-level information that explains episodes hidden by national improvement.

The seven-month report deserves attention as part of a continuing series. A later annual release can confirm, qualify or reverse the interim direction, and that revision should be treated as learning rather than failure. Its correct question is not whether environmental quality has been permanently solved, but whether several independent measures, after weather and season are considered, continue to move in a healthier direction.
'@
Add-Env 26 6 'Seven Months Are a Signal, Not a Year' $c '页面可访问；核验2026年前7个月全国空气和水环境质量改善的报道口径；正文严格限定部分年度数据的季节性含义。' 'Partial-year environmental data require seasonal, meteorological and spatial context before supporting durable conclusions.' 'Its correct question is not whether environmental quality has been permanently solved, but whether several independent measures, after weather and season are considered, continue to move in a healthier direction.' 'Why is a year-on-year comparison still affected by nature?' 'Weather can alter dispersion, dilution and runoff even across matched months.' 'It does not eliminate weather.' 'discontinuity' 'a sharp category change created by crossing a threshold' 'a threshold creates discontinuity.' 'A compliance rate can hide substantial improvement that remains just outside the standard.' 'a large reduction that remains just above the line disappears from the compliance total.' 'The author treats uncertainty disclosure as a source of authority rather than weakness.' 'Public reporting gains authority by showing revisions, missing observations and uncertainty.'

$c=@'
Balancing high-quality development with strong environmental protection is often presented as a search for compromise, as if each side began with a fixed claim and policy simply split the difference. That image is too static. Development choices change future environmental options, while environmental quality changes productivity, health costs and resilience. The balance must be designed over time.

An industrial park illustrates the point. Strict entry standards may reject a polluting project today, but shared clean-energy, water-reuse and waste-exchange infrastructure can also attract firms able to operate more efficiently. Protection is then not only a constraint; it becomes part of the park's productive capacity. This outcome is not automatic, because expensive infrastructure without suitable users can waste resources.

Regulation needs both floors and incentives. Emission limits protect against unacceptable harm. Market signals can reward performance beyond the minimum, but trading systems depend on accurate baselines and enforcement. If firms expect weak penalties or can shift pollution to contractors, a low reported cost may represent transferred damage rather than efficiency.

Distribution matters across places and generations. Closing an obsolete facility can improve regional air while concentrating job losses in one town. Transition support should be assessed as seriously as equipment investment: retraining must connect with actual vacancies, and local finance may need a replacement base. Future residents also deserve protection from liabilities hidden in contaminated land or long-lived carbon assets.

High-quality development therefore needs outcome definitions broad enough to include health, resource productivity, ecosystem stability and opportunity. Gross output remains informative, but it cannot represent costs that are unpaid today and unavoidable tomorrow. Environmental assessment is most useful early, while location and technology can still change, rather than after construction turns alternatives into compensation disputes.

The desired balance is dynamic consistency: short-term projects should preserve or enlarge the capacity for later prosperity under ecological limits. Strong protection and development align when institutions expose hidden costs, support affected people and reward designs that reduce total pressure instead of relocating it.
'@
Add-Env 27 6 'Balance Is a Design Across Time' $c '页面可访问；核验报道关于以高水平保护支撑高质量发展、绿色转型和污染防治的政策主线。' 'Development and protection align through institutions that account for long-term costs, distribution and ecological limits.' 'Strong protection and development align when institutions expose hidden costs, support affected people and reward designs that reduce total pressure instead of relocating it.' 'How can environmental infrastructure strengthen an industrial park?' 'It can attract firms capable of efficient shared energy, water and material systems.' 'shared clean-energy, water-reuse and waste-exchange infrastructure can also attract firms able to operate more efficiently.' 'dynamic consistency' 'making present choices preserve future prosperity within ecological limits' 'The desired balance is dynamic consistency' 'A cheap compliance result may conceal pollution shifted to contractors.' 'a low reported cost may represent transferred damage rather than efficiency.' 'The author rejects both a simple trade-off and the claim that alignment happens automatically.' 'This outcome is not automatic, because expensive infrastructure without suitable users can waste resources.'

$c=@'
Officials were preparing another policy package in 2026 to keep air pollution declining over time. The word sustained changes the policy problem. Emergency controls can lower pollution during a short episode, but durable gains require changes in energy, industry, transport, construction dust and regional coordination that remain effective when attention moves elsewhere.

An action plan needs a causal map, not merely a longer list of measures. Pollution sources contribute differently by season and region. Fine particles may be emitted directly or formed in the atmosphere from several gases; ozone control can involve chemical relationships in which reducing one precursor alone does not always produce the expected local result. Source inventories and atmospheric modeling should guide priorities, then observations should test those models.

Targets can combine average exposure, severe episodes and population distribution. A national concentration decline might coexist with neighborhoods beside freight roads or industrial sites receiving little benefit. Monitoring expansion should therefore prioritize gaps that matter for health, not only locations convenient for maintaining a stable trend. Personal exposure studies can complement fixed stations without replacing them.

Implementation must survive economic and meteorological variation. Firms need predictable standards for investment, while regulators require authority to respond to unusual events. Temporary production restrictions may be justified during severe pollution, but repeated emergency use can indicate that structural sources remain untreated. Evaluation should distinguish avoided episodes from activity merely shifted to another week or jurisdiction.

Regional transport makes accountability harder. Upwind controls can benefit downwind cities, so isolated local scorecards may discourage cooperation. Joint forecasts, aligned standards and shared review can recognize contributions without erasing local responsibility. Data should be released quickly enough for public use and revised openly when instruments or methods change.

A sustained plan succeeds when cleaner air becomes the normal result of ordinary systems rather than an exceptional achievement produced for inspection. Periodic independent review can test whether enforcement and investment remain effective outside headline episodes. Its ambition is institutional memory: rules, investment and monitoring continue learning after the launch headline has faded.
'@
Add-Env 28 6 'Sustained Clean Air Requires Institutional Memory' $c '页面可访问；核验2026年正在制定持续改善空气质量新行动计划的报道事实及多污染物、区域协同治理方向。' 'A sustained air plan must convert temporary control into adaptive, evidence-based ordinary systems.' 'A sustained plan succeeds when cleaner air becomes the normal result of ordinary systems rather than an exceptional achievement produced for inspection. Periodic independent review can test whether enforcement and investment remain effective outside headline episodes.' 'Why can one-precursor control give an unexpected ozone result?' 'Atmospheric chemistry links several gases differently across local conditions.' 'ozone control can involve chemical relationships in which reducing one precursor alone does not always produce the expected local result.' 'causal map' 'an account connecting sources, processes, interventions and measured outcomes' 'An action plan needs a causal map, not merely a longer list of measures.' 'Frequent emergency restrictions may reveal unfinished structural reform.' 'repeated emergency use can indicate that structural sources remain untreated.' 'The author favors rapid public data release together with transparent later correction.' 'Data should be released quickly enough for public use and revised openly when instruments or methods change.'

$c=@'
Measures issued in 2026 set out a way to assess progress in building a Beautiful China. The phrase deliberately reaches beyond one pollutant or agency. That breadth can encourage integrated governance, but an assessment framework must translate aspiration into indicators without pretending that everything valuable fits one score.

A layered design can separate environmental pressure, condition, public service and governance capacity. Pressure indicators describe emissions or resource use; condition indicators measure air, water, soil or ecosystems; service indicators ask whether people can reach green space or reliable waste systems; capacity indicators examine monitoring and enforcement. Improvement in one layer should not automatically cancel deterioration in another.

Weighting is therefore a political and technical choice. If abundant national data receive the greatest weight, poorly measured biodiversity or rural exposure may appear unimportant. If every indicator is weighted equally, a minor administrative task can offset severe ecological loss. The framework should publish why weights were chosen and test whether rankings change under reasonable alternatives.

Assessment can also distort behavior. Local authorities may focus on indicators easiest to improve before review, move pollution across boundaries or avoid reporting uncertainty. Independent audits, stable definitions and checks for unintended consequences reduce these incentives. Qualitative evidence remains useful where numbers cannot yet represent ecosystem integrity or public experience, provided judgment criteria are explicit.

Comparability and local relevance pull in different directions. A shared core allows national learning, while additional regional measures can reflect deserts, coasts, dense cities or major watersheds. The result should not become a league table that punishes places for inherited conditions. Evaluation should emphasize credible improvement, absolute safeguards and duties appropriate to local pressures.

Finally, assessment must feed decisions. A score that appears once a year but does not change budgets, permits or restoration plans is ceremonial. A useful review identifies causes, assigns follow-up and records whether correction worked.

Beautiful can guide policy precisely because it invites a whole-system question. Its credibility, however, rests on a transparent architecture that keeps unlike values visible, resists gaming and turns measurement into accountable learning.
'@
Add-Env 29 6 'How to Measure Beauty Without Hiding Damage' $c '页面可访问；核验2026年发布美丽中国建设成效考核措施的报道事实；正文围绕多层指标、权重与问责原创分析。' 'A Beautiful China assessment needs transparent layers, anti-gaming safeguards and a route from measurement to correction.' 'Its credibility, however, rests on a transparent architecture that keeps unlike values visible, resists gaming and turns measurement into accountable learning.' 'Which four layers can an integrated review distinguish?' 'Pressure, environmental condition, public service and governance capacity.' 'A layered design can separate environmental pressure, condition, public service and governance capacity.' 'weighting' 'assigning different influence to indicators in a combined evaluation' 'Weighting is therefore a political and technical choice.' 'A national core can coexist with region-specific measures without forcing identical conditions.' 'A shared core allows national learning, while additional regional measures can reflect deserts, coasts, dense cities or major watersheds.' 'The author regards an annual score as inadequate unless it changes decisions and tracks correction.' 'A score that appears once a year but does not change budgets, permits or restoration plans is ceremonial.'

$c=@'
China reported improvement in air and water quality during the first half of 2026. Half-year data are substantial enough to reveal patterns, yet they remain an interim account. The temptation is to turn direction into completion, especially when a national average provides a clear headline and the underlying monitoring network is far more complex.

Air indicators combine concentrations, attainment days and sometimes severe episodes. Water assessment classifies monitored sections by intended uses and measured substances. These systems are not directly additive: a one-point improvement in an air metric cannot compensate for deterioration in a drinking-water source. An integrated report should place results beside one another while preserving their separate safeguards.

Attribution is another challenge. Policy affects emissions, wastewater treatment and land management, but weather and hydrology change measured concentrations. A dry period can reduce dilution in rivers; unusual winds can alter regional air transport. Statistical adjustment is helpful only when assumptions and uncertainty are visible. Otherwise, a technically corrected number may appear more certain than the original observation.

National progress can mask unequal exposure. Population-weighted metrics show what the average person experiences, while area-based summaries reveal geographic reach. Neither alone captures vulnerable groups close to industrial sources or communities dependent on a particular river. Disaggregated maps, episode records and complaint data can reveal where the direction of change differs from the headline.

Monitoring itself is a public institution. Instruments require calibration, stations need protection from interference, and revisions should remain in an audit trail. New sensors can improve spatial coverage, but inexpensive devices should be compared with reference equipment before their data carry regulatory consequences. Openness includes explaining why a value changed after quality control.

The first half of a year should trigger operational questions: which measures appear durable, which regions lag, and what conditions could reverse progress? Those questions turn reporting into management.

Environmental improvement deserves recognition without losing precision. The most trustworthy headline is one that invites readers into the evidence beneath it and remains ready to change when the second half of the year completes the picture.
'@
Add-Env 30 6 'A Half-Year Headline Must Remain Revisable' $c '页面可访问；核验2026年上半年全国空气、水环境质量改善的报道口径；正文将其作为可修订的阶段性证据。' 'Interim environmental improvement should prompt disaggregated, auditable management rather than a final national verdict.' 'The most trustworthy headline is one that invites readers into the evidence beneath it and remains ready to change when the second half of the year completes the picture.' 'Why should air and water gains remain separate in an integrated report?' 'Their metrics and safeguards are not interchangeable or additive.' 'These systems are not directly additive: a one-point improvement in an air metric cannot compensate for deterioration in a drinking-water source.' 'audit trail' 'a preserved record of measurements, checks and later revisions' 'revisions should remain in an audit trail.' 'Cheaper sensors need comparison with reference equipment before regulatory use.' 'inexpensive devices should be compared with reference equipment before their data carry regulatory consequences.' 'The author welcomes improvement while treating the headline as provisional.' 'Half-year data are substantial enough to reveal patterns, yet they remain an interim account.'

$out=[IO.Path]::Combine([IO.Path]::GetTempPath(),'environment-generated.json')
$items | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $out -Encoding UTF8
Write-Host ('wrote {0} articles to {1}' -f $items.Count,$out)






