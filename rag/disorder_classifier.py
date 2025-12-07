from typing import Optional

def classify_disorder(dsm_name: str) -> Optional[str]:
    d = dsm_name.strip()

    depressive_keywords = [
        "Major Depressive Disorder",
        "Persistent Depressive Disorder",
        "Premenstrual Dysphoric Disorder",
    ]
    if d in depressive_keywords:
        return "Depressive Disorders"

    anxiety_exact = [
        "Generalized Anxiety Disorder",
        "Panic Disorder",
        "Agoraphobia",
        "Social Anxiety Disorder",
        "Specific Phobia",
        "Separation Anxiety Disorder",
        "Selective Mutism",
    ]
    if d in anxiety_exact:
        return "Anxiety Disorders"

    bipolar_exact = [
        "Bipolar I Disorder",
        "Bipolar II Disorder",
        "Cyclothymic Disorder",
    ]
    if d in bipolar_exact:
        return "Bipolar and Related Disorders"

    psychotic_exact = [
        "Schizophrenia",
        "Schizoaffective Disorder",
        "Schizophreniform Disorder",
        "Brief Psychotic Disorder",
        "Delusional Disorder",
    ]
    if d in psychotic_exact:
        return "Schizophrenia / Psychotic Disorders"

    ocd_exact = [
        "Obsessive-Compulsive Disorder",
        "Body Dysmorphic Disorder",
        "Hoarding Disorder",
        "Trichotillomania",
        "Excoriation (Skin-Picking) Disorder",
    ]
    if d in ocd_exact:
        return "Obsessive-Compulsive and Related Disorders"

    dissociative_exact = [
        "Dissociative Amnesia",
        "Dissociative Identity Disorder",
        "Depersonalization/Derealization Disorder",
    ]
    if d in dissociative_exact:
        return "Dissociative Disorders"

    if d.endswith("Personality Disorder"):
        return "Personality Disorders"

    adhd_exact = [
        "Attention-Deficit/Hyperactivity Disorder",
        "Oppositional Defiant Disorder",
        "Conduct Disorder",
        "Intermittent Explosive Disorder",
    ]
    if d in adhd_exact:
        return "Attention-Deficit/Hyperactivity Disorder"

    substance_keywords = ("Use Disorder", "Intoxication", "Withdrawal")
    if any(k in d for k in substance_keywords):
        return "Addiction / Substance Use & Gambling"
    if d == "Gambling Disorder":
        return "Addiction / Substance Use & Gambling"

    ptsd_exact = [
        "Posttraumatic Stress Disorder",
        "Acute Stress Disorder",
        "Adjustment Disorders",
    ]
    if d in ptsd_exact:
        return "Posttraumatic Stress Disorder"

    return None
