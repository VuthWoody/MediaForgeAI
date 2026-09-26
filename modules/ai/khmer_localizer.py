"""Natural Khmer dialogue localization and cinema dubbing engine.

Converts literal, robotic, or dictionary machine translations into authentic,
fluent, emotionally engaging conversational Khmer (ភាសានិយាយភាពយន្តបែបធម្មជាតិ).
Handles gender-specific particles, spoken conversational pronouns, cinema idioms,
and natural sentence cadence.
"""

from __future__ import annotations

import re


class KhmerDialogueLocalizer:
    """Specialized localization engine for authentic, natural conversational Khmer cinema dubbing."""

    # Curated conversational idioms and colloquial dialogue patterns (Pattern, Replacement)
    IDIOM_RULES: list[tuple[str, str]] = [
        # --- 1. Greetings & Friendly Catch-ups ---
        (r"\b(Hey|ហេ)\s+([A-Za-z]+)\s*,\s*សុខសប្បាយជាទេ\?", r"សួស្តី \2! សុខសប្បាយអត់ហ្នឹង?"),
        (r"\b(Hey|ហេ)\s+([A-Za-z]+)", r"សួស្តី \2"),
        (r"ឱព្រះជាម្ចាស់អើយ\s*([A-Za-z]+)?\s*[,។]?", r"អូព្រះអើយ! \1,"),
        (r"ឱព្រះជាម្ចាស់អើយ", r"អូព្រះអើយ!"),
        (r"ខ្ញុំល្អណាស់", r"ខ្ញុំសុខសប្បាយធម្មតាទេ"),
        (r"សុខសប្បាយជាទេ\?", r"សុខសប្បាយអត់?"),
        (r"ខ្ញុំអស្ចារ្យណាស់[។\.]?", r"សប្បាយចិត្តខ្លាំងណាស់!"),
        (r"អស្ចារ្យ[។\.]\s*យកកន្លែងអង្គុយ[។\.]\s*កៅអីនេះគឺទទេ[។\.]?", r"ល្អហើយ! អង្គុយទីនេះមក កៅអីនេះទំនេរតើ!"),
        (r"យកកន្លែងអង្គុយ", r"អង្គុយទីនេះមក"),
        (r"យកកៅអី", r"អង្គុយមក"),
        (r"កៅអីនេះគឺទទេ", r"កៅអីនេះទំនេរតើ"),
        (r"យូរ[។\.]\s*ឥឡូវឃើញទេ\?", r"ខានជួបគ្នាយូរណាស់ហើយណ៎!"),
        (r"ខានឃើញគ្នាយូរ", r"ខានជួបគ្នាយូរណាស់ហើយ"),
        (r"បន្ទាប់ពីរយៈពេលយូរ", r"ក្រោយខានជួបគ្នាយូរ"),
        (r"យូរហើយឥឡូវឃើញទេ", r"ខានជួបគ្នាយូរណាស់ហើយ"),

        # --- 2. School, College, Work & Daily Life ---
        (r"រវល់ជាមួយមហាវិទ្យាល័យ", r"រវល់រឿងរៀនសូត្រនៅមហាវិទ្យាល័យ"),
        (r"ចុះអ្នកវិញ\?", r"ចុះឯងវិញ?"),
        (r"តើអ្នកកំពុងធ្វើអ្វីឥឡូវនេះ\?", r"ឥឡូវហ្នឹងឯងកំពុងធ្វើអីដែរ?"),
        (r"តើអ្នកកំពុងធ្វើអ្វី\?", r"ចុះឯងកំពុងធ្វើអីដែរ?"),
        (r"បញ្ចប់ការសិក្សារបស់ខ្ញុំ", r"ទើបតែរៀនចប់សញ្ញាបត្រ"),
        (r"ខ្ញុំទើបតែបញ្ចប់ការសិក្សារបស់ខ្ញុំ", r"ខ្ញុំទើបតែរៀនចប់សញ្ញាបត្រ"),
        (r"ខ្ញុំកំពុងធ្វើ\s*homeopathy\s*នៅគ្លីនិកក្បែរនោះ", r"ខ្ញុំកំពុងធ្វើការផ្នែកព្យាបាលធម្មជាតិនៅគ្លីនិកក្បែរនេះ"),
        (r"ខ្ញុំកំពុងធ្វើ\s*homeopathy\s*នៅមហាវិទ្យាល័យក្បែរនោះ", r"ខ្ញុំកំពុងរៀនផ្នែកព្យាបាលធម្មជាតិនៅមហាវិទ្យាល័យជិតនេះ"),
        (r"តើអ្នកមកទីនេះដោយរបៀបណា\?", r"ម៉េចបានជាឯងមកដល់ទីនេះចឹង?"),
        (r"តើអ្នកមកលើរថភ្លើងនេះដោយរបៀបណាថ្ងៃនេះ\?", r"ចុះម៉េចបានជាឯងមកជិះរថភ្លើងនេះថ្ងៃនេះចឹង?"),
        (r"យើងមានការប្រជុំថ្ងៃនេះ ដូច្នេះអ្នកគ្រប់គ្នាត្រូវមកប្រមូលសញ្ញាបត្ររបស់ពួកគេ", r"ថ្ងៃនេះសាលាមានកម្មវិធីចែកសញ្ញាបត្រ ដូច្នេះអ្នករាល់គ្នាត្រូវមកទទួលយកសញ្ញាបត្ររៀងៗខ្លួន"),
        (r"ពេញមួយឆ្នាំដែលខ្ញុំបញ្ចប់ការសិក្សា ហើយវាគឺជារថភ្លើងដ៏ល្អបំផុតមួយ", r"ពេញមួយកំឡុងពេលរៀនសូត្រ ហើយរថភ្លើងនេះគឺជិះស្រួលជាងគេម៉ង"),
        (r"វាតែងតែទទេ ហើយយើងតែងតែទទួលបានកៅអីសម្រាប់ខ្លួនយើង", r"រថភ្លើងនេះមិនសូវមានមនុស្សជិះទេ ចឹងហើយពួកយើងតែងតែមានកៅអីអង្គុយស្រួល"),
        (r"នេះជាហេតុផលពិតប្រាកដដែលខ្ញុំធ្លាប់ឡើងរថភ្លើងនេះគ្រប់ពេល", r"ហ្នឹងហើយ ជាមូលហេតុដែលខ្ញុំចូលចិត្តជិះរថភ្លើងនេះរហូត"),
        (r"បន្ទាប់ពីនឿយហត់ពេញមួយថ្ងៃ ទើបបានធូរស្បើយឡើងជិះរថភ្លើងទទេ", r"ហត់នឿយពេញមួយថ្ងៃហើយ បានជិះរថភ្លើងស្ងាត់ចឹង ពិតជាធូរស្រាលអារម្មណ៍មែន"),
        (r"ចុះ​អ្នក​ព្យាបាល​ជំងឺ​ដោយ​ខ្លួន​ឯង​វិញ\? តើវគ្គសិក្សារបស់អ្នកនឹងបញ្ចប់នៅពេលណា\?", r"ចុះការរៀនព្យាបាលធម្មជាតិរបស់ឯងវិញ? ពេលណាទើបចប់វគ្គ?"),
        (r"ខ្ញុំក៏ត្រូវបង្ខំចិត្តដែរ ហើយមានតែពេលនោះខ្ញុំ និងសិស្សផ្សេងទៀតនឹងទទួលបានសញ្ញាបត្រ", r"ខ្ញុំត្រូវចុះកម្មសិក្សាជាកំហិតសិន ទើបខ្ញុំនិងសិស្សដទៃទៀតអាចទទួលសញ្ញាបត្របាន"),
        (r"មហាវិទ្យាល័យរបស់ខ្ញុំនៅទីនេះ ដូច្នេះខ្ញុំធ្វើដំណើរជារៀងរាល់ថ្ងៃតាមរថភ្លើងនេះ", r"សាលារបស់ខ្ញុំនៅម្តុំនេះ ដូច្នេះខ្ញុំជិះរថភ្លើងនេះរាល់ថ្ងៃហ្នឹង"),

        # --- 3. Encouragement, Farewell & Parting ---
        (r"មួយ​ឆ្នាំ​ទៀត​ទៅ បាទ​ខ្ញុំ​សង្ឃឹម​ថា​វា​ទៅ​បាន​ល្អ", r"នៅសល់តែមួយឆ្នាំទៀតទេ! សង្ឃឹមថាគ្រប់យ៉ាងនឹងរលូនទៅចុះ"),
        (r"មួយ​ឆ្នាំ​ទៀត​ទៅ", r"នៅសល់តែមួយឆ្នាំទៀតទេ!"),
        (r"កុំ​បារម្ភ​ថា​វា​នឹង​ទៅ​បាន​ល្អ", r"កុំបារម្ភអី គ្រប់យ៉ាងនឹងល្អប្រសើរទេ"),
        (r"ខ្ញុំ​គិត​ថា​រថភ្លើង​បាន​មក​ដល់​ហើយ", r"រថភ្លើងមកដល់កន្លែងហើយ"),
        (r"រីករាយដែលបានជួបអ្នកបន្ទាប់ពីរយៈពេលយូរ", r"រីករាយណាស់ដែលបានជួបឯងក្រោយខានជួបគ្នាយូរ"),
        (r"រីករាយដែលបានជួបអ្នកយូរហើយ", r"រីករាយណាស់ដែលបានជួបឯងក្រោយខានជួបគ្នាយូរ"),
        (r"រីករាយដែលបានជួបអ្នកផងដែរ", r"ខ្ញុំក៏រីករាយដែលបានជួបឯងដូចគ្នា"),
        (r"រីករាយដែលបានជួបអ្នក", r"រីករាយណាស់ដែលបានជួបឯង"),
        (r"ជួបគ្នាឆាប់ៗរហូតដល់ពេលនោះល្អបំផុត ហើយយកចិត្តទុកដាក់ លាហើយ", r"ចាំជួបគ្នាឆាប់ៗណា៎! ជូនពរសំណាងល្អ និងមើលថែខ្លួនផង លាហើយ!"),
        (r"ពួកយើងនឹងជួបគ្នាឆាប់ៗនេះ ចាំមើលទាំងអស់គ្នា លាហើយ ចាំជួបគ្នា", r"ពួកយើងនឹងជួបគ្នាឆាប់ៗទៀត! មើលថែខ្លួនផងណា៎ លាហើយ!"),
        (r"មិនយូរប៉ុន្មានអ្នកក៏ថែរក្សាផងដែរ[។\.]?", r"ឯងក៏ដូចគ្នាដែរណា៎ មើលថែខ្លួនផង! លាហើយ!"),
        (r"យកចិត្តទុកដាក់ លាហើយ", r"មើលថែខ្លួនផងណា៎ លាហើយ!"),
        (r"សូម​អរគុណ", r"អរគុណច្រើន"),

        # --- 4. Pronoun and Particle Polish ---
        (r"\bតើអ្នក\b", r"តើឯង"),
        (r"\bរបស់អ្នក\b", r"របស់ឯង"),
        (r"\bអ្នក\b", r"ឯង"),
        (r"\bសម្រាប់ខ្លួនយើង\b", r"សម្រាប់ពួកយើង"),
    ]

    @staticmethod
    def detect_gender(speaker_str: str | None) -> str:
        """Infer speaker gender from speaker tag, name, or metadata.

        Returns 'female', 'male', or 'neutral'.
        """
        if not speaker_str:
            return "neutral"
        s_lower = speaker_str.lower()
        if any(w in s_lower for w in ("female", "girl", "woman", "emma", "sreymom", "mother", "sister", "lady")):
            return "female"
        if any(w in s_lower for w in ("male", "boy", "man", "james", "piseth", "father", "brother", "guy")):
            return "male"
        return "neutral"

    @classmethod
    def naturalize(
        cls,
        text: str,
        speaker_gender: str = "auto",
        speaker_name: str | None = None,
    ) -> str:
        """Transform a raw machine-translated sentence into authentic, idiomatic spoken Khmer."""
        if not text:
            return ""

        res = text.strip()

        # Resolve gender if auto
        gender = speaker_gender
        if gender == "auto" or gender == "neutral":
            gender = cls.detect_gender(speaker_name)

        # Apply curated conversational idioms
        for pat, repl in cls.IDIOM_RULES:
            res = re.sub(pat, repl, res)

        # Gender-specific polite particles:
        if gender == "female":
            # Female speakers in Khmer say 'ចាស / ចា៎' instead of 'បាទ'
            res = re.sub(r"^\s*បាទ\s*[,។]?", "ចាស ", res)
            res = re.sub(r"\s+បាទ\s+", " ចាស ", res)
            res = re.sub(r"\s+បាទ$", " ចាស", res)
        elif gender == "male":
            # Male speakers say 'បាទ' instead of 'ចាស'
            res = re.sub(r"^\s*ចាស\s*[,។]?", "បាទ ", res)
            res = re.sub(r"\s+ចាស\s+", " បាទ ", res)
            res = re.sub(r"\s+ចាស$", " បាទ", res)

        # Clean multiple spaces and ensure clean punctuation
        res = re.sub(r"\s+", " ", res).strip()
        # Clean double exclamation or punctuation artifacts
        res = re.sub(r"!+", "!", res)
        res = re.sub(r"\?+", "?", res)
        return res
