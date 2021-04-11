#!/usr/bin/python

"""
    The analyser is the entrypoint for the analysis
    >>> analyser = GitAnalyser('repos/django')
    >>> analyser.analyse()
    >>> analyser.output_html('django_analysis.html')
"""

import git
import datetime as dt
import argparse
import json


__version__ = '0.0.1'


class AnalysisEmptyError(Exception):
    pass


class GitAnalyser:
    # DATE_FMT to be used for x-axis timeline in chart
    DATE_FMT = '%b-%Y'
    TEMPLATE_FILE = 'chart_template.html'
    DATE_RANGE_FMT = '%d/%m/%Y'

    def __init__(self, repo_path):
        self.repo = git.Repo(repo_path)

        self.filter_date_flag = False
        self.start_date = dt.date(year=2005, month=1, day=1)
        self.end_date = dt.date(year=2006, month=8, day=1)

        self.filter_authors_flag = False
        self.target_authors = []

        self.cmt_dates = []
        self.cmt_info = {}
        self.final_graph_data = {}
        self._tracked_commits = []

    def set_date_range(self, start_date_str, end_date_str):
        self.start_date = dt.datetime.strptime(start_date_str, self.DATE_RANGE_FMT).date()
        self.end_date = dt.datetime.strptime(end_date_str, self.DATE_RANGE_FMT).date()

    def _add_cmt_info(self, author, date_str, cmt_obj):
        stats = cmt_obj.stats.total
        insertions = stats.get('insertions', 0)
        deletions = stats.get('deletions', 0)

        # author-wise mapping
        if author not in self.cmt_info:
            self.cmt_info[author] = {}

        if date_str not in self.cmt_info[author]:
            self.cmt_info[author][date_str] = {
                "commits": 1,
                "insertions": insertions,
                "deletions": deletions
            }
        else:
            self.cmt_info[author][date_str]['commits'] += 1
            self.cmt_info[author][date_str]['insertions'] += insertions
            self.cmt_info[author][date_str]['deletions'] += deletions

    def _is_analysis_empty(self):
        return not self.cmt_info

    def analyse_branch(self, branch):
        for cmt in self.repo.iter_commits(rev=branch):
            author = cmt.author.email
            if self.filter_authors_flag and self.target_authors and author not in self.target_authors:
                continue

            cmt_date = cmt.committed_datetime.date()
            if self.filter_date_flag and not (self.start_date <= cmt_date <= self.end_date):
                continue

            cmt_date_str = cmt_date.strftime(self.DATE_FMT)

            if cmt.hexsha not in self._tracked_commits:
                self._tracked_commits.append(cmt.hexsha)

                self._add_cmt_info(author, cmt_date_str, cmt)

                if cmt_date_str not in self.cmt_dates:
                    self.cmt_dates.append(cmt_date_str)

    def analyse(self):
        # iterate over all branch's commits and analyse commits
        for (i, ref) in enumerate(self.repo.refs):
            print(f'{i+1}/{len(self.repo.refs)}. Checking commits for {ref}')
            self.analyse_branch(ref)

        # sorted_dates = list(self.cmt_dates)
        # sorted_dates.sort(key=lambda d: dt.datetime.strptime(d, self.DATE_FMT))
        self.prepare_graph_data()

    def prepare_graph_data(self):
        if self._is_analysis_empty():
            raise AnalysisEmptyError("No analysis data found")

        series_data = []
        authors = []

        for (author, ci) in self.cmt_info.items():
            authors.append(author)
            commit_data = [
                {
                    "name": "Commits",
                    "value": ci.get(cmt_date, {}).get('commits', 0),
                    "commits": ci.get(cmt_date, {}).get('commits', 0),
                    "insertions": ci.get(cmt_date, {}).get('insertions', 0),
                    "deletions": ci.get(cmt_date, {}).get('deletions', 0),
                } for cmt_date in self.cmt_dates[::-1]
            ]

            # use {}.update in javascript and only update name and data
            series_data.append({
                "name": author,
                "type": 'bar',
                "barGap": 0,
                "emphasis": {
                    "focus": 'series'
                },
                "data": commit_data
            })

        self.final_graph_data = {
            "title": f'"{self.cmt_dates[0]} - {self.cmt_dates[-1]} Commits"',
            "legend_data": authors,
            "xaxis_data": self.cmt_dates,
            "series_data": json.dumps(series_data, indent=4)
        }

    def output_html(self, outfile):
        print(f'Generating {outfile} file')
        from jinja2 import Template

        with open(self.TEMPLATE_FILE) as fd:
            rendered_chart_file = Template(fd.read()).render(chart_data=self.final_graph_data)

        with open(outfile, 'w') as fd:
            fd.write(rendered_chart_file)

    def output_json(self):
        raise NotImplementedError("This function is not implemented yet")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Analyse repository and generate analysis report in "+
        "given html file"
    )

    parser.add_argument(
        "repo_path",
        help="Path of the git repository to use for analysis"
    )
    parser.add_argument(
        "--out-file",
        required=False,
        help="The output file name",
        default='git_analysis.html'
    )

    args = parser.parse_args()

    try:
        analyser = GitAnalyser(args.repo_path)
        analyser.analyse()
        analyser.output_html(args.out_file)

        print('Done!')
    except AnalysisEmptyError as exc:
        print('[ ERROR ]', exc)
    except git.exc.NoSuchPathError as exc:
        print('[ ERROR ] Invalid Repository Path', args.repo_path)
    except FileNotFoundError as exc:
        print('[ ERROR ]', exc)
