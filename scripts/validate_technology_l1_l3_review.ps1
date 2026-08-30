$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root 'seed\review_batches\technology_l1_l3_manual.json'
$batch = Get-Content -Raw -Encoding UTF8 -LiteralPath $target | ConvertFrom-Json
$articles = @($batch.passages)
$errors = [System.Collections.Generic.List[string]]::new()
$bounds = @{1=@(180,230);2=@(210,260);3=@(240,300)}
$required = @('corpus_id','source_id','title','topic','difficulty','source_name','source_url','source_title','source_published_at','retrieved_at','source_verification','adaptation_note','content','questions')

function Words([string]$Text) { return @([regex]::Matches($Text.ToLowerInvariant(), "[a-z]+(?:'[a-z]+)?") | ForEach-Object Value) }
function Grams([string]$Text, [int]$N) {
    $tokens = @(Words $Text)
    $set = [System.Collections.Generic.HashSet[string]]::new()
    for ($i=0; $i -le $tokens.Count-$N; $i++) { [void]$set.Add(($tokens[$i..($i+$N-1)] -join ' ')) }
    Write-Output -NoEnumerate $set
}
function Similarity($Left, $Right) {
    if ($Left.Count -eq 0 -and $Right.Count -eq 0) { return 0.0 }
    $intersection = 0
    foreach ($value in $Left) { if ($Right.Contains($value)) { $intersection++ } }
    return $intersection / [math]::Max(1, ($Left.Count + $Right.Count - $intersection))
}

if ($articles.Count -ne 15) { $errors.Add("passage_count=$($articles.Count)") }
foreach ($level in 1..3) {
    $count = @($articles | Where-Object difficulty -eq $level).Count
    if ($count -ne 5) { $errors.Add("level_${level}_count=$count") }
}
foreach ($field in @('corpus_id','source_id','title','source_url','source_title')) {
    $duplicates = @($articles | Group-Object $field | Where-Object Count -gt 1)
    if ($duplicates) { $errors.Add("duplicate_$field") }
}
$stems = [System.Collections.Generic.HashSet[string]]::new()
foreach ($article in $articles) {
    foreach ($field in $required) { if (-not $article.$field) { $errors.Add("$($article.corpus_id):missing_$field") } }
    $level = [int]$article.difficulty
    $wordCount = @(Words $article.content).Count
    if ($wordCount -lt $bounds[$level][0] -or $wordCount -gt $bounds[$level][1]) { $errors.Add("$($article.corpus_id):words=$wordCount") }
    if ($article.topic -ne '科技') { $errors.Add("$($article.corpus_id):topic") }
    if ($article.source_url -notmatch '^https://(english\.news\.cn|global\.chinadaily\.com\.cn)/') { $errors.Add("$($article.corpus_id):host") }
    if (@($article.questions).Count -ne 5) { $errors.Add("$($article.corpus_id):question_count") }
    if (@($article.questions.type | Sort-Object -Unique).Count -lt 4) { $errors.Add("$($article.corpus_id):type_variety") }
    $inferences = @($article.questions | Where-Object type -eq 'inference').Count
    if (($level -eq 1 -and $inferences -gt 1) -or ($level -eq 2 -and $inferences -ne 1) -or ($level -eq 3 -and ($inferences -lt 1 -or $inferences -gt 2))) { $errors.Add("$($article.corpus_id):inference=$inferences") }
    foreach ($question in $article.questions) {
        $normalized = ([regex]::Replace($question.question.ToLowerInvariant(), '[^a-z0-9]+', ' ')).Trim()
        if (-not $stems.Add($normalized)) { $errors.Add("$($article.corpus_id):duplicate_stem=$normalized") }
        if (@($question.options).Count -ne 4 -or @($question.options | Sort-Object -Unique).Count -ne 4) { $errors.Add("$($article.corpus_id):options") }
        if ([string]$question.answer -notmatch '^[ABCD]$') { $errors.Add("$($article.corpus_id):answer") }
        if ($question.explanation -notmatch '[\u4e00-\u9fff]') { $errors.Add("$($article.corpus_id):explanation") }
        $evidenceCount = ([regex]::Matches($article.content, [regex]::Escape([string]$question.evidence_text))).Count
        if ($evidenceCount -ne 1) { $errors.Add("$($article.corpus_id):evidence_count=$evidenceCount") }
    }
}

$allArticles = [System.Collections.Generic.List[object]]::new()
Get-ChildItem (Join-Path $root 'seed\reading_corpus') -Filter '*.json' | ForEach-Object {
    if ($_.BaseName -ne '科技') {
        (Get-Content -Raw -Encoding UTF8 -LiteralPath $_.FullName | ConvertFrom-Json) | ForEach-Object { $allArticles.Add($_) }
    }
}
foreach ($name in @('technology_l1_l3_manual.json','technology_l4_l6_manual.json')) {
    $path = Join-Path $root "seed\review_batches\$name"
    if (Test-Path $path) { (Get-Content -Raw -Encoding UTF8 -LiteralPath $path | ConvertFrom-Json).passages | ForEach-Object { $allArticles.Add($_) } }
}
foreach ($field in @('corpus_id','title','source_url','source_title')) {
    $duplicates = @($allArticles | Group-Object $field | Where-Object Count -gt 1)
    if ($duplicates) { $errors.Add("combined_duplicate_$field=$($duplicates.Name -join '|')") }
}
$contentGrams = @($allArticles | ForEach-Object { [pscustomobject]@{id=$_.corpus_id; grams=(Grams $_.content 5)} })
$maxContent = [pscustomobject]@{value=0.0; pair=''}
for ($i=0; $i -lt $contentGrams.Count; $i++) {
    for ($j=$i+1; $j -lt $contentGrams.Count; $j++) {
        $similarity = Similarity $contentGrams[$i].grams $contentGrams[$j].grams
        if ($similarity -gt $maxContent.value) { $maxContent=[pscustomobject]@{value=$similarity;pair="$($contentGrams[$i].id) / $($contentGrams[$j].id)"} }
        if ($similarity -gt 0.12) { $errors.Add("content_5gram=$similarity $($contentGrams[$i].id)/$($contentGrams[$j].id)") }
    }
}
$questionRows = @($allArticles | ForEach-Object { $id=$_.corpus_id; $_.questions | ForEach-Object { [pscustomobject]@{id=$id;text=$_.question;grams=(Grams $_.question 5)} } })
$maxStem = [pscustomobject]@{value=0.0; pair=''}
for ($i=0; $i -lt $questionRows.Count; $i++) {
    for ($j=$i+1; $j -lt $questionRows.Count; $j++) {
        $similarity = Similarity $questionRows[$i].grams $questionRows[$j].grams
        if ($similarity -gt $maxStem.value) { $maxStem=[pscustomobject]@{value=$similarity;pair="$($questionRows[$i].id) / $($questionRows[$j].id)"} }
        if ($similarity -gt 0.12 -and ($questionRows[$i].id -like 'cet-manual-technology-l[123]-*' -or $questionRows[$j].id -like 'cet-manual-technology-l[123]-*')) { $errors.Add("stem_5gram=$similarity $($questionRows[$i].text) / $($questionRows[$j].text)") }
    }
}
$answerCounts = $articles.questions.answer | Group-Object | ForEach-Object { "$($_.Name):$($_.Count)" }
[ordered]@{
    passages=$articles.Count
    levels=[ordered]@{L1=@($articles|Where-Object difficulty -eq 1).Count;L2=@($articles|Where-Object difficulty -eq 2).Count;L3=@($articles|Where-Object difficulty -eq 3).Count}
    answer_distribution=($answerCounts -join ', ')
    max_content_5gram=[math]::Round($maxContent.value,4)
    max_content_pair=$maxContent.pair
    max_stem_5gram=[math]::Round($maxStem.value,4)
    max_stem_pair=$maxStem.pair
    errors=$errors
} | ConvertTo-Json -Depth 6
if ($errors.Count) { exit 1 }
