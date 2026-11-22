# Research

The evidence behind the app: what makes dyslexia in Arabic different, why each activity was chosen, how the app
compares with existing tools, and what the adult pilot measured. Full references are at the end.

The app is a practice and support tool. It makes no clinical claims, and the app itself has not yet been tested with
children.

## 1. Dyslexia in Arabic

| Feature of Arabic | Why it matters | What the app does |
|---|---|---|
| Short vowels are marks above and below letters; long vowels are letters | Vowel dyslexia, a selective difficulty with vowel letters that includes reading short vowels as long and long as short, was one of the most frequent types in an Arabic sample (Friedmann & Haddad-Hanna 2014) | Scores vowels and vowel length, not only consonants |
| Letters that differ only by their dots: ب ت ث، ج ح خ، د ذ، ر ز، س ش، ص ض، ط ظ، ع غ، ف ق | Arabic's equivalent of b/d. Visual-orthographic errors, which include dot errors, were over a quarter of all spelling errors in grades 1, 2 and 4 (Yassin et al. 2020) | A dedicated error type and practice built on these pairs |
| Letters can migrate within a word | Letter position dyslexia is a described Arabic type (Friedmann & Haddad-Hanna 2014) | Detects swapped letters |
| Children speak a dialect but read Modern Standard Arabic | Diglossia, vowelization and morphology are the three features that shape Arabic word reading (Saiegh-Haddad 2018) | Starts with common words; dialect tolerance is future work |

**Prevalence.** A meta-analysis of 18 studies in Arab countries (30,243 children aged 6–13) found a pooled
prevalence of developmental dyslexia of 11%, higher in Gulf countries (24% against 13%, from 8 Gulf studies)
(Aldakhil 2024).

## 2. How the activities connect to the evidence

Arabic dyslexia shows itself in specific errors. A reader improves on an error when told about it precisely and soon,
so the app listens sound by sound and names the error instead of accepting a near miss. It then practises the weak
sounds in four activities, one for each layer of reading, and knowledge tracing links them so that a mistake in one
shapes practice in all of them.

| Layer | Activity | Main evidence | What we took from it |
|---|---|---|---|
| Sounds | Sound Surgery | National Reading Panel (NICHD 2000; Ehri et al. 2001) | Two kinds of sound manipulation, done on the written word |
| Words | Word Flash | Reading Acceleration Program (Horowitz-Kraus et al. 2014) | Display time set just above the reader's own pace |
| Timing | Rhythmic Reading | Flaugnacco et al. 2015; Bonacina et al. 2015; Cancer & Antonietti 2022 | Words read in time with a beat |
| Text | My Story | Therrien 2004; Lee & Yoon 2017 | The same passage read up to three times |
| All | Feedback and coach | Wisniewski et al. 2020 | Say exactly what went wrong |
| All | Adaptive practice | Corbett & Anderson 1995 | Mastery of each sound decides the next words |

Most of this evidence comes from other languages, and none of it tests this app. We claim what each method has shown,
not that the app improves reading.

### Sound Surgery (phonemic awareness)

The National Reading Panel meta-analysis found a large effect of phonemic awareness instruction on phonemic awareness
(d = 0.86) and a moderate effect on reading (d = 0.53). Programmes that taught one or two kinds of sound manipulation
did better than those teaching three or more, and programmes that had children manipulate sounds with letters did
best (Ehri et al. 2001; NICHD 2000). Sound Surgery uses two manipulations, deletion and substitution, on the written
word.

Arabic studies are small but point the same way. In Layes et al. (2019), 20 Algerian children with dyslexia who had
phonological training outperformed a control group of 20 in word and pseudoword reading and phonological processing.
Al Farsi and Imam (2017) randomly assigned 14 Omani children with reading disabilities and found gains in
phonological awareness and decoding.

### Word Flash (reading at a brief display)

In the Reading Acceleration Program, text disappears at the reader's own fastest pace. In 89 Hebrew- and
English-speaking children with reading difficulties, the trained groups improved in silent reading speed,
comprehension and speed of processing after four weeks. The Hebrew-speaking trained group also read faster and more
accurately and understood more than its waiting list; the English-speaking group gained less (Horowitz-Kraus et al.
2014).

### Rhythmic Reading

In a randomised trial with 46 Italian children with dyslexia, 30 weeks of rhythm-based music classes gave larger gains
in pseudoword reading accuracy, verbal working memory and auditory attention than painting classes, with no difference
in reading speed (Flaugnacco et al. 2015). Rhythmic Reading Training, a computer program in which children read
syllables and words on screen in time with a rhythm that gradually speeds up, improved pseudoword reading speed
(Bonacina et al. 2015; Cancer et al. 2020). A review of 18 studies found music training, and music or auditory
training combined with reading, the most effective forms; auditory training alone did not carry over to reading
(Cancer & Antonietti 2022). The samples are small and none of the studies is in Arabic.

### My Story (repeated reading)

Rereading the same passage improved fluency (0.83) and comprehension (0.67) in a meta-analysis; on new passages the
effects were 0.50 and 0.25. Three readings gave a larger fluency effect than two (0.85 against 0.57), and the author
recommends three to four (Therrien 2004). For students with reading disabilities, the pre-to-post fluency gain was
g = 1.41, without a control group (Lee & Yoon 2017).

The evidence has limits. Chard et al. (2009) judged the research base too small to call repeated reading
evidence-based for students with learning disabilities, the What Works Clearinghouse (2014) found no discernible
effect on their fluency, and a randomised Arabic study of 44 children found no fluency gain (Almotoe 2019). Building
the story from the child's own mistakes is our design, not a tested method.

### Feedback and the reading coach

A meta-analysis of 435 studies found a medium effect of feedback on learning (d = 0.48). Feedback that says what went
wrong and how to improve had the largest effect (d = 0.99), against 0.46 for simple right-or-wrong feedback
(Wisniewski et al. 2020). The app names the sound that went wrong and what it heard instead. The coach, a language
model, only explains a result the scorer has already decided; its own effect has not been measured.

### Adaptive practice

Bayesian Knowledge Tracing estimates mastery of each skill from right and wrong answers and is widely used in
tutoring systems (Corbett & Anderson 1995). It is a modelling method, so we make no claim about its effect on reading.

## 3. Existing tools

| Tool | What it does | Difference |
|---|---|---|
| Google Read Along | Listens to children read Arabic stories and gives feedback; deliberately "permissive", leaning towards accepting a pronunciation (Khaleej Times 2020) | General reading, not dyslexia. Accepting near misses hides the errors that matter here (short vowels, dots) |
| Mila-Learn (France) | Rhythm games for dyslexia | French; does not listen to reading |
| Sinbad and Jasmin (Kuwait, 2019) | Adaptive short-term memory training | No reading or speech; no published outcomes |
| Screening tools (e.g. SARD, UAE) | Screen for reading difficulties | Screening, not practice |

We found no Arabic dyslexia app that scores reading aloud sound by sound.

## 4. Adult pilot

Four consenting adults aged 18 to 24, speaking Kuwaiti, Qatari, Egyptian and Libyan Arabic, each read 24 cards
(`ml/pilot_items.csv`) on their own phones: 8 words as written and 16 with a planted error, 96 recordings in all. A
listener wrote down what each reader actually said, and `ml/pilot.py` compared the app's verdict with that.

Readers did not always make the planted error: shown a near-word such as جِمَلْ, several read the real word جَمَل
without noticing, and an Egyptian reader said ق as g. Labelled by what was said, 37 recordings were correct readings
and 59 contained a real error.

| Measure | Result |
|---|---|
| App's verdict matches the listener | 84% (81 of 96) |
| Real errors caught | 83% (49 of 59) |
| Correct readings marked right | 32 of 37 (3 asked to read again, 2 marked wrong) |
| When the app says wrong, it is a real error | 91% |
| Error type named as the listener would | 41% |

All 10 missed errors were transcribed correctly by the speech model and then accepted by the fit check
([design.md](design.md), section 3). Nearly all were a single short vowel or vowel length, such as سَمِكْ for سَمَكْ.
Asking for a second reading in that case is the next change to test. Swapped letters were caught but often named as
substitutions, which explains most of the low type agreement.

Limits: four adults, planted errors, and one listener who knew the intended answer. No children and no readers with
dyslexia. With 59 errors, the true catch rate could plausibly be anywhere from about 72% to 91%.

## 5. Pilot ethics

- Adults only, each with a signed consent form in Arabic and English ([pilot-consent.md](pilot-consent.md)).
- Only a code, age band and dialect are stored; no names with recordings.
- Recordings are processed on our own computer, never sent to an outside service, and never committed to this
  repository. Raw audio is deleted by 31 December 2026; only scores and error counts are kept.
- The app says "practice", never "test", and gives no clinical judgement.

## 6. Display choices

Extra letter spacing improved text reading in Italian and French children with dyslexia (Zorzi et al. 2012). The app
uses large text, a clear naskh face, wide spacing and a right-to-left layout.

## References

- Aldakhil, A. F. (2024). Prevalence of developmental dyslexia among primary school children in Arab countries: A systematic review and meta-analysis. *Research in Developmental Disabilities, 152*, 104812.
- Al Farsi, H. A., & Imam, M. M. (2017). Effectiveness of phonological awareness skills training in improving decoding skills of children with reading disabilities. *Journal of Educational and Psychological Studies, 11*(2), 315–336.
- Almotoe, A. (2019). *The effects of peer-mediated repeated reading on reading fluency and comprehension for students with reading difficulties* [Doctoral dissertation, University of Iowa].
- Bonacina, S., Cancer, A., Lanzi, P. L., Lorusso, M. L., & Antonietti, A. (2015). Improving reading skills in students with dyslexia: The efficacy of a sublexical training with rhythmic background. *Frontiers in Psychology, 6*, 1510.
- Cancer, A., & Antonietti, A. (2022). Music-based and auditory-based interventions for reading difficulties: A literature review. *Heliyon, 8*(4), e09293.
- Cancer, A., Bonacina, S., Antonietti, A., Salandi, A., Molteni, M., & Lorusso, M. L. (2020). The effectiveness of interventions for developmental dyslexia: Rhythmic reading training compared with hemisphere-specific stimulation and action video games. *Frontiers in Psychology, 11*, 1158.
- Chard, D. J., Ketterlin-Geller, L. R., Baker, S. K., Doabler, C., & Apichatabutra, C. (2009). Repeated reading interventions for students with learning disabilities: Status of the evidence. *Exceptional Children, 75*(3), 263–281.
- Corbett, A. T., & Anderson, J. R. (1995). Knowledge tracing: Modeling the acquisition of procedural knowledge. *User Modeling and User-Adapted Interaction, 4*(4), 253–278.
- Ehri, L. C., Nunes, S. R., Willows, D. M., Schuster, B. V., Yaghoub-Zadeh, Z., & Shanahan, T. (2001). Phonemic awareness instruction helps children learn to read: Evidence from the National Reading Panel's meta-analysis. *Reading Research Quarterly, 36*(3), 250–287.
- Flaugnacco, E., Lopez, L., Terribili, C., Montico, M., Zoia, S., & Schön, D. (2015). Music training increases phonological awareness and reading skills in developmental dyslexia: A randomized control trial. *PLoS ONE, 10*(9), e0138715.
- Friedmann, N., & Haddad-Hanna, M. (2014). Types of developmental dyslexia in Arabic. In E. Saiegh-Haddad & R. M. Joshi (Eds.), *Handbook of Arabic literacy: Insights and perspectives* (pp. 119–151). Springer.
- Horowitz-Kraus, T., Cicchino, N., Amiel, M., Holland, S. K., & Breznitz, Z. (2014). Reading improvement in English- and Hebrew-speaking children with reading difficulties after reading acceleration training. *Annals of Dyslexia, 64*(3), 183–201.
- Khaleej Times. (2020, September 13). Free Google app aims to help kids improve their Arabic reading skills.
- Layes, S., Lalonde, R., & Rebai, M. (2019). Effects of an adaptive phonological training program on reading and phonological processing skills in Arabic-speaking children with dyslexia. *Reading & Writing Quarterly, 35*(2), 103–117.
- Lee, J., & Yoon, S. Y. (2017). The effects of repeated reading on reading fluency for students with reading disabilities: A meta-analysis. *Journal of Learning Disabilities, 50*(2), 213–224.
- National Institute of Child Health and Human Development. (2000). *Report of the National Reading Panel. Teaching children to read* (NIH Publication No. 00-4769). U.S. Government Printing Office.
- Saiegh-Haddad, E. (2018). MAWRID: A model of Arabic word reading in development. *Journal of Learning Disabilities, 51*(5), 454–462.
- Therrien, W. J. (2004). Fluency and comprehension gains as a result of repeated reading: A meta-analysis. *Remedial and Special Education, 25*(4), 252–261.
- What Works Clearinghouse. (2014, May). *Students with learning disabilities intervention report: Repeated reading*. U.S. Department of Education, Institute of Education Sciences.
- Wisniewski, B., Zierer, K., & Hattie, J. (2020). The power of feedback revisited: A meta-analysis of educational feedback research. *Frontiers in Psychology, 10*, 3087.
- Yassin, R., Share, D. L., & Shalhoub-Awwad, Y. (2020). Learning to spell in Arabic: The impact of script-specific visual-orthographic features. *Frontiers in Psychology, 11*, 2059.
- Zorzi, M., Barbiero, C., Facoetti, A., Lonciari, I., Carrozzi, M., Montico, M., Bravar, L., George, F., Pech-Georgel, C., & Ziegler, J. C. (2012). Extra-large letter spacing improves reading in dyslexia. *Proceedings of the National Academy of Sciences, 109*(28), 11455–11459.
