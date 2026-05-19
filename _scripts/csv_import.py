import csv


def import_csv(filename):
    with open(filename, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def main():
    words = import_csv("Terms.csv")
    formatted_words = [w["term"] for w in words]
    write_plain_text("lute_words.txt", formatted_words)


def write_plain_text(filename, words):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(words))


if __name__ == "__main__":
    main()
