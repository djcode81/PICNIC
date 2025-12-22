#!/usr/bin/env python3

# update_old_summary_report

from pathlib import Path
import argparse
import rich
import re
import shutil


# Override python native print with the rich version
from rich import print

# Some globals


def get_env(args):
    """ Integrate environment variables into our args. """

    return args


class App:
    def __init__(self):
        self.args = self.get_arguments()
        self.args = get_env(self.args)
        self.validate_args()

        self.updated_html = ""

    def validate_args(self):
        """ Ensure the environment will support the requested workflows. """

        if Path(self.args.report_path).exists():
            if self.args.verbose:
                print(f"Path '{self.args.report_path}' exists.")
        else:
            print(f"[red]Path '{self.args.report_path}' does not exist.[/red]")

    @staticmethod
    def get_arguments():
        """ Parse command line arguments """

        parser = argparse.ArgumentParser(
            description="PICNIC run prior to Dec 2025 did not include papaya code. "
                        "This script will update the report with papaya javascript.",
        )
        parser.add_argument(
            "report_path",
            help="The final summary html file output by PICNIC",
        )
        parser.add_argument(
            "--verbose", action="store_true",
            help="set to trigger verbose output",
        )

        return parser.parse_args()

    def get_reconall_subdir(self):
        """ Find the subdir, relative to the html, with reconall images. """
        for subdir in Path(self.args.report_path).parent.glob("*reconall"):
            return subdir.name
        return None

    def remove_broken_links(self):
        """ PICNIC writes a movie link to a non-existent file. """

        length_removed = 0  # to adjust indices after updated_html changes
        # pre_html_length = len(self.updated_html)
        matches = list(re.finditer(
            r"<video.*\s*.*<source src=[\"\'](.*)[\"\']/>.*\s*.*/video>",
            self.updated_html,
        ))
        # Traverse in reverse so updates don't invalidate indices
        for match in reversed(matches):
            if (Path(self.args.report_path).parent / match.group(1)).exists():
                if self.args.verbose:
                    print(f"  Found '{match.group(1)}'")
            else:
                if self.args.verbose:
                    print(f"  Missing '{match.group(1)}', removing link")
                    # print(f"  removing '\n{self.updated_html[match.start():match.end()]}\n'")
                self.updated_html = "\n".join([
                    self.updated_html[:match.start() - length_removed].rstrip(),
                    self.updated_html[match.end() + 1 - length_removed:]
                ])
                # length_removed = len(self.updated_html) - pre_html_length
                # if self.args.verbose:
                #     print(f"  Adjusted indices by {length_removed} characters")

    def insert_papaya_code(self):
        """ Insert papaya javascript into the report. """

        cdn_papaya_url = "https://cdn.jsdelivr.net/gh/bil-mind-nyspi/PICNIC@main/src/papaya"
        reconall_subdir = self.get_reconall_subdir()

        if "script" in self.updated_html:
            print(f"A script is already in the html, not inserting papaya.")
        elif reconall_subdir is None:
            print(f"No reconall subdir found, not inserting papaya.")
        else:
            # Insert link to papaya.css into the head
            head_match = re.search(
                r"<head>(.*)</head>",
                self.updated_html,
                flags=re.DOTALL
            )
            if head_match:
                print(f"No script tag in the html, inserting papaya css.")
                self.updated_html = "\n".join([
                    self.updated_html[:head_match.start() + 6],
                    f"    <link rel=\"stylesheet\" type=\"text/css\" href=\"{cdn_papaya_url}/papaya.css\" />",
                    self.updated_html[head_match.start() + 6:]
                ])
            else:
                print(f"No head tag found.")

            # Insert javascript into the end of the body
            # Note that udpated_html changed above, so the search must be done fresh
            body_match = re.search(
                r"<body>(.*)</body>",
                self.updated_html,
                flags=re.DOTALL
            )
            if body_match:
                # Write the javascript necessary to prepopulate papaya with configured images
                path_lines = []
                prop_lines = []
                for stem, props in [
                    ("T1", "lut: \"Grayscale\", alpha: 0.00"),
                    ("subcortical_mask", "color: [1.0, 1.0, 0.8], min: 0.0, max: 1.1, alpha: 0.20"),
                    ("ventricle_mask", "color: [1.0, 0.1, 0.1], min: 0.0, max: 1.1, alpha: 0.20"),
                    ("wm_mask", "color: [0.0, 0.0, 1.0], min: 0.0, max: 1.1, alpha: 0.20"),
                    ("gm_mask", "color: [0.0, 0.5, 0.1], min: 0.0, max: 1.1, alpha: 0.20"),
                    ("bilateral_wmparc", "min: 0, max: 15000, alpha: 0.50, lut: new FreeSurferLUT()"),
                ]:
                    if (Path(self.args.report_path).parent / f"{reconall_subdir}/{stem}.nii.gz").exists():
                        path_lines.append(f"            \"{reconall_subdir}/{stem}.nii.gz\",")
                        prop_lines.append(f"        anat_params[\"{stem}.nii.gz\"] = {{{props}}};")
                    else:
                        print(f"[red]  missing {reconall_subdir}/{stem}.nii.gz, leaving it out of papaya.[/red]")
                papaya_js_lines = [
                    f"    <script type=\"text/javascript\" src=\"{cdn_papaya_url}/papaya.js\"></script>",
                    f"    <script type=\"text/javascript\" src=\"{cdn_papaya_url}/freesurferlut.js\"></script>",
                    "    <script>""",
                    "        var anat_params = [];",
                    "        anat_params[\"worldSpace\"] = false;",
                    "        anat_params[\"showOrientation\"] = true;",
                    "        anat_params[\"radiological\"] = true;",
                    "        anat_params[\"images\"] = [",
                ] + path_lines + [
                    "        ];",
                ] + prop_lines + [
                    "    </script>""",
                ]

                # Back up to the last '\n' before the </body> tag.
                i = body_match.end()
                insertion_point = body_match.end() - 7
                while self.updated_html[insertion_point - 1] != "\n":
                    insertion_point -= 1
                self.updated_html = "\n".join([
                    self.updated_html[:insertion_point],
                    *papaya_js_lines,
                    self.updated_html[insertion_point:]
                ])

            else:
                print(f"No body tag found.")

    def backup_original(self):
        """ Back up the original html """

        src_path = Path(self.args.report_path)
        # Default backup name: replace ".html" with ".orig.html"
        if src_path.name.endswith('.html'):
            backup_name = src_path.name[:-5] + '.orig.html'
        else:
            # Fallback: append .orig
            backup_name = src_path.name + '.orig'
        backup_path = src_path.with_name(backup_name)

        # If backup exists, add incrementing numbers before the final .html
        if backup_path.exists():
            counter = 1
            if backup_path.suffix == '.html' and backup_path.name.endswith('.orig.html'):
                stem = backup_path.name[:-10]  # strip '.orig.html'
                while True:
                    candidate = src_path.with_name(f"{stem}.orig.{counter}.html")
                    if not candidate.exists():
                        backup_path = candidate
                        break
                    counter += 1
            else:
                # Generic fallback numbering
                while True:
                    candidate = backup_path.with_name(f"{backup_path.name}.{counter}")
                    if not candidate.exists():
                        backup_path = candidate
                        break
                    counter += 1

        shutil.copy2(src_path, backup_path)
        if self.args.verbose:
            print(f"Created backup: {backup_path}")


    def run(self):
        """ Run the app. """

        # First, back up the original html file.
        self.backup_original()

        # Read the html file.
        with open(self.args.report_path, "r") as f:
            self.updated_html = f.read()
            if self.args.verbose:
                print(f"Read {len(self.updated_html)} characters from {self.args.report_path}")

        # PICNIC writes a movie link to a non-existent file.
        self.remove_broken_links()

        # Ensure papaya javascript is present.
        self.insert_papaya_code()

        # Write the updated version to the original file path.
        with open(self.args.report_path, "w") as f:
            f.write(self.updated_html)
        if self.args.verbose:
            print(f"Wrote {len(self.updated_html)} characters to {self.args.report_path}")

def main():
    """ Entry point """

    app = App()
    app.run()


if __name__ == "__main__":
    main()
