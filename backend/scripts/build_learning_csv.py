"""Build data/kb/learning_resources.csv for EVERY canonical taxonomy skill.

Columns: skill,title,url_documentation,url_youtube
Docs URLs are official documentation (spot-verified via web for risky ones);
YouTube links are per-skill tutorial SEARCHES (never invented video IDs),
qualified with a famous creator only for ultra-famous pairings.

    python scripts/build_learning_csv.py [--check-only]
"""
import csv
import sys
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import SKILL_TAXONOMY_CSV

OUT = Path(__file__).resolve().parents[2] / "data" / "kb" / "learning_resources.csv"
YT = "https://www.youtube.com/results?search_query="

# skill -> (title, docs_url, youtube query suffix or None for plain "<skill> full course")
DOCS: dict[str, tuple[str, str, str | None]] = {
    # ---- languages ----
    "Python": ("Python Tutorial", "https://docs.python.org/3/tutorial/", "freeCodeCamp"),
    "JavaScript": ("JavaScript Guide (MDN)", "https://developer.mozilla.org/en-US/docs/Web/JavaScript", None),
    "TypeScript": ("TypeScript Handbook", "https://www.typescriptlang.org/docs/handbook/intro.html", None),
    "Java": ("Java Tutorials", "https://docs.oracle.com/javase/tutorial/", None),
    "C": ("C Programming Reference", "https://en.cppreference.com/w/c", None),
    "C++": ("C++ Reference", "https://en.cppreference.com/w/", None),
    "C#": ("C# Guide", "https://learn.microsoft.com/en-us/dotnet/csharp/", None),
    "Go": ("Go Documentation", "https://go.dev/doc/", None),
    "Rust": ("The Rust Book", "https://doc.rust-lang.org/book/", None),
    "PHP": ("PHP Manual", "https://www.php.net/manual/en/", None),
    "Swift": ("Swift Documentation", "https://www.swift.org/documentation/", None),
    "Kotlin": ("Kotlin Docs", "https://kotlinlang.org/docs/home.html", None),
    "Dart": ("Dart Guides", "https://dart.dev/guides", None),
    "Ruby": ("Ruby Documentation", "https://www.ruby-lang.org/en/documentation/", None),
    "Scala": ("Scala Documentation", "https://docs.scala-lang.org/", None),
    "Haskell": ("Haskell Documentation", "https://www.haskell.org/documentation/", None),
    "Perl": ("Perl Documentation", "https://perldoc.perl.org/", None),
    "R": ("R Introduction", "https://cran.r-project.org/doc/manuals/r-release/R-intro.html", None),
    "Julia": ("Julia Documentation", "https://docs.julialang.org/en/v1/", None),
    "MATLAB": ("MATLAB Documentation", "https://www.mathworks.com/help/matlab/", None),
    "SQL": ("SQL Tutorial", "https://sqlbolt.com/", None),
    "HTML": ("HTML Guide (MDN)", "https://developer.mozilla.org/en-US/docs/Web/HTML", None),
    "CSS": ("CSS Guide (MDN)", "https://developer.mozilla.org/en-US/docs/Web/CSS", None),
    "Bash": ("Bash Manual", "https://www.gnu.org/software/bash/manual/", None),
    "PowerShell": ("PowerShell Docs", "https://learn.microsoft.com/en-us/powershell/", None),
    "Elixir": ("Elixir Getting Started", "https://elixir-lang.org/getting-started/introduction.html", None),
    # ---- frontend ----
    "React": ("React Learn", "https://react.dev/learn", "Traversy Media"),
    "Angular": ("Angular Docs", "https://angular.dev/", None),
    "Vue.js": ("Vue Guide", "https://vuejs.org/guide/introduction.html", None),
    "Svelte": ("Svelte Docs", "https://svelte.dev/docs", None),
    "Next.js": ("Next.js Learn", "https://nextjs.org/learn", "JavaScript Mastery"),
    "Nuxt.js": ("Nuxt Docs", "https://nuxt.com/docs/getting-started/introduction", None),
    "Tailwind CSS": ("Tailwind Docs", "https://tailwindcss.com/docs", None),
    "Bootstrap": ("Bootstrap Docs", "https://getbootstrap.com/docs/5.3/getting-started/introduction/", None),
    "Sass": ("Sass Documentation", "https://sass-lang.com/documentation/", None),
    "Less": ("Less Docs", "https://lesscss.org/", None),
    "Material UI": ("MUI Docs", "https://mui.com/material-ui/getting-started/", None),
    "shadcn/ui": ("shadcn/ui Docs", "https://ui.shadcn.com/docs", None),
    "Framer Motion": ("Motion Docs", "https://motion.dev/docs", None),
    "Three.js": ("Three.js Manual", "https://threejs.org/manual/", None),
    "D3.js": ("D3 Getting Started", "https://d3js.org/getting-started", None),
    "Storybook": ("Storybook Docs", "https://storybook.js.org/docs", None),
    "Styled Components": ("styled-components Docs", "https://styled-components.com/docs", None),
    "Zustand": ("Zustand Guide", "https://zustand.docs.pmnd.rs/getting-started/introduction", None),
    "Redux": ("Redux Essentials", "https://redux.js.org/introduction/getting-started", None),
    "Axios": ("Axios Docs", "https://axios-http.com/docs/intro", None),
    "jQuery": ("jQuery API", "https://api.jquery.com/", None),
    "Vite": ("Vite Guide", "https://vite.dev/guide/", None),
    "Webpack": ("Webpack Concepts", "https://webpack.js.org/concepts/", None),
    "Babel": ("Babel Docs", "https://babeljs.io/docs/", None),
    "ESLint": ("ESLint Docs", "https://eslint.org/docs/latest/", None),
    "Prettier": ("Prettier Docs", "https://prettier.io/docs/en/", None),
    "Enzyme": ("Enzyme Docs", "https://enzymejs.github.io/enzyme/", None),
    "Vitest": ("Vitest Guide", "https://vitest.dev/guide/", None),
    # ---- backend ----
    "Node.js": ("Node.js Learn", "https://nodejs.org/en/learn", "Piyush Garg"),
    "Express.js": ("Express Guide", "https://expressjs.com/en/guide/routing.html", None),
    "NestJS": ("NestJS Docs", "https://docs.nestjs.com/", None),
    "FastAPI": ("FastAPI Tutorial", "https://fastapi.tiangolo.com/tutorial/", None),
    "Flask": ("Flask Docs", "https://flask.palletsprojects.com/", None),
    "Django": ("Django Docs", "https://docs.djangoproject.com/", None),
    "Spring Boot": ("Spring Boot Docs", "https://docs.spring.io/spring-boot/", None),
    "Laravel": ("Laravel Docs", "https://laravel.com/docs", None),
    "Ruby on Rails": ("Rails Guides", "https://guides.rubyonrails.org/", None),
    "ASP.NET": ("ASP.NET Core Docs", "https://learn.microsoft.com/en-us/aspnet/core/", None),
    "GraphQL": ("GraphQL Learn", "https://graphql.org/learn/", None),
    "REST API": ("REST Tutorial", "https://www.restapitutorial.com/", None),
    "gRPC": ("gRPC Docs", "https://grpc.io/docs/", None),
    "WebSockets": ("WebSockets Guide (MDN)", "https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API", None),
    "Socket.io": ("Socket.IO Docs", "https://socket.io/docs/v4/", None),
    "tRPC": ("tRPC Docs", "https://trpc.io/docs", None),
    "Kafka": ("Kafka Documentation", "https://kafka.apache.org/documentation/", None),
    "RabbitMQ": ("RabbitMQ Docs", "https://www.rabbitmq.com/docs", None),
    "BullMQ": ("BullMQ Guide", "https://docs.bullmq.io/", None),
    "Celery": ("Celery Docs", "https://docs.celeryq.dev/en/stable/", None),
    "Prisma": ("Prisma Docs", "https://www.prisma.io/docs", None),
    "TypeORM": ("TypeORM Docs", "https://typeorm.io/", None),
    "Drizzle": ("Drizzle Docs", "https://orm.drizzle.team/docs/overview", None),
    "Sequelize": ("Sequelize Docs", "https://sequelize.org/docs/v6/", None),
    "SQLAlchemy": ("SQLAlchemy Docs", "https://docs.sqlalchemy.org/", None),
    "Mongoose": ("Mongoose Docs", "https://mongoosejs.com/docs/", None),
    "Microservices": ("Microservices Guide", "https://microservices.io/", None),
    "Serverless": ("Serverless Docs", "https://www.serverless.com/framework/docs", None),
    "Bun": ("Bun Docs", "https://bun.sh/docs", None),
    # ---- databases ----
    "PostgreSQL": ("PostgreSQL Tutorial", "https://www.postgresql.org/docs/current/tutorial.html", None),
    "MySQL": ("MySQL Docs", "https://dev.mysql.com/doc/", None),
    "MongoDB": ("MongoDB Docs", "https://www.mongodb.com/docs/", None),
    "Redis": ("Redis Docs", "https://redis.io/docs/latest/", None),
    "SQLite": ("SQLite Docs", "https://www.sqlite.org/docs.html", None),
    "SQL Server": ("SQL Server Docs", "https://learn.microsoft.com/en-us/sql/", None),
    "Oracle DB": ("Oracle Database Docs", "https://docs.oracle.com/database", None),
    "MariaDB": ("MariaDB Docs", "https://mariadb.com/kb/en/documentation/", None),
    "Cassandra": ("Cassandra Docs", "https://cassandra.apache.org/doc/latest/", None),
    "Elasticsearch": ("Elastic Guide", "https://www.elastic.co/guide/", None),
    "Neo4j": ("Neo4j Docs", "https://neo4j.com/docs/", None),
    "DynamoDB": ("DynamoDB Guide", "https://docs.aws.amazon.com/dynamodb/", None),
    "Firestore": ("Firestore Docs", "https://firebase.google.com/docs/firestore", None),
    "BigQuery": ("BigQuery Docs", "https://cloud.google.com/bigquery/docs", None),
    "Snowflake": ("Snowflake Docs", "https://docs.snowflake.com/", None),
    "Redshift": ("Redshift Guide", "https://docs.aws.amazon.com/redshift/", None),
    "Pinecone": ("Pinecone Docs", "https://docs.pinecone.io/", None),
    "Qdrant": ("Qdrant Docs", "https://qdrant.tech/documentation/", None),
    "ChromaDB": ("Chroma Docs", "https://docs.trychroma.com/", None),
    "pgvector": ("pgvector Guide", "https://github.com/pgvector/pgvector", None),
    "Supabase": ("Supabase Docs", "https://supabase.com/docs", None),
    # ---- devops ----
    "Docker": ("Docker Get Started", "https://docs.docker.com/get-started/", "TechWorld with Nana"),
    "Kubernetes": ("Kubernetes Basics", "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "TechWorld with Nana"),
    "Jenkins": ("Jenkins Docs", "https://www.jenkins.io/doc/", None),
    "Ansible": ("Ansible Docs", "https://docs.ansible.com/", None),
    "Terraform": ("Terraform Docs", "https://developer.hashicorp.com/terraform/docs", None),
    "GitHub Actions": ("Actions Docs", "https://docs.github.com/en/actions", None),
    "GitLab CI": ("GitLab CI Docs", "https://docs.gitlab.com/ee/ci/", None),
    "CircleCI": ("CircleCI Docs", "https://circleci.com/docs/", None),
    "Nginx": ("nginx Docs", "https://nginx.org/en/docs/", None),
    "Apache": ("Apache Docs", "https://httpd.apache.org/docs/", None),
    "Linux": ("Kernel Docs", "https://docs.kernel.org/", None),
    "Prometheus": ("Prometheus Docs", "https://prometheus.io/docs/introduction/overview/", None),
    "Grafana": ("Grafana Docs", "https://grafana.com/docs/", None),
    "Datadog": ("Datadog Docs", "https://docs.datadoghq.com/", None),
    "ELK Stack": ("Elastic Guide", "https://www.elastic.co/guide/", None),
    "CI/CD": ("GitLab CI/CD Docs", "https://docs.gitlab.com/ee/ci/", None),
    # ---- cloud ----
    "AWS": ("AWS Skill Builder", "https://skillbuilder.aws/", "freeCodeCamp"),
    "Azure": ("Azure Docs", "https://learn.microsoft.com/en-us/azure/", None),
    "GCP": ("Google Cloud Docs", "https://cloud.google.com/docs", None),
    "EC2": ("EC2 Docs", "https://docs.aws.amazon.com/ec2/", None),
    "S3": ("S3 Docs", "https://docs.aws.amazon.com/s3/", None),
    "Lambda": ("Lambda Guide", "https://docs.aws.amazon.com/lambda/", None),
    "RDS": ("RDS Docs", "https://docs.aws.amazon.com/rds/", None),
    "ECR": ("ECR Docs", "https://docs.aws.amazon.com/ecr/", None),
    "ECS": ("ECS Guide", "https://docs.aws.amazon.com/ecs/", None),
    "Fargate": ("Fargate Guide", "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html", None),
    "CloudFormation": ("CloudFormation Docs", "https://docs.aws.amazon.com/cloudformation/", None),
    "CloudWatch": ("CloudWatch Docs", "https://docs.aws.amazon.com/cloudwatch/", None),
    "SQS": ("SQS Guide", "https://docs.aws.amazon.com/sqs/", None),
    "SNS": ("SNS Guide", "https://docs.aws.amazon.com/sns/", None),
    "IAM": ("IAM Docs", "https://docs.aws.amazon.com/iam/", None),
    "Heroku": ("Heroku Dev Center", "https://devcenter.heroku.com/", None),
    "Netlify": ("Netlify Docs", "https://docs.netlify.com/", None),
    "Vercel": ("Vercel Docs", "https://vercel.com/docs", None),
    "Render": ("Render Docs", "https://render.com/docs", None),
    "Railway": ("Railway Docs", "https://docs.railway.com/", None),
    "DigitalOcean": ("DigitalOcean Docs", "https://docs.digitalocean.com/", None),
    "Cloudflare": ("Cloudflare Docs", "https://developers.cloudflare.com/", None),
    # ---- data ----
    "Pandas": ("Pandas Docs", "https://pandas.pydata.org/docs/", None),
    "NumPy": ("NumPy Docs", "https://numpy.org/doc/", None),
    "Matplotlib": ("Matplotlib Tutorials", "https://matplotlib.org/stable/tutorials/index.html", None),
    "Seaborn": ("Seaborn Tutorial", "https://seaborn.pydata.org/tutorial.html", None),
    "Plotly": ("Plotly Python", "https://plotly.com/python/", None),
    "Jupyter": ("Jupyter Docs", "https://docs.jupyter.org/", None),
    "Hadoop": ("Hadoop Docs", "https://hadoop.apache.org/docs/", None),
    "Spark": ("Spark Docs", "https://spark.apache.org/docs/latest/", None),
    "Airflow": ("Airflow Docs", "https://airflow.apache.org/docs/", None),
    "dbt": ("dbt Docs", "https://docs.getdbt.com/", None),
    "ETL": ("IBM ETL Guide", "https://www.ibm.com/topics/etl", None),
    "Excel": ("Excel Support", "https://support.microsoft.com/en-us/excel", None),
    "Power BI": ("Power BI Docs", "https://learn.microsoft.com/en-us/power-bi/", None),
    "Tableau": ("Tableau Training", "https://www.tableau.com/learn/training", None),
    "Statistics": ("Khan Statistics", "https://www.khanacademy.org/math/statistics-probability", None),
    "Airbyte": ("Airbyte Docs", "https://docs.airbyte.com/", None),
    "Fivetran": ("Fivetran Docs", "https://fivetran.com/docs", None),
    # ---- ML ----
    "TensorFlow": ("TensorFlow Tutorials", "https://www.tensorflow.org/tutorials", "freeCodeCamp"),
    "PyTorch": ("PyTorch Tutorials", "https://pytorch.org/tutorials/", None),
    "Keras": ("Keras Docs", "https://keras.io/", None),
    "Scikit-learn": ("Scikit-learn Docs", "https://scikit-learn.org/stable/", None),
    "Hugging Face": ("Hugging Face Docs", "https://huggingface.co/docs", None),
    "LangChain": ("LangChain Docs", "https://python.langchain.com/docs/introduction/", None),
    "LangGraph": ("LangGraph Docs", "https://langchain-ai.github.io/langgraph/", None),
    "LlamaIndex": ("LlamaIndex Docs", "https://docs.llamaindex.ai/", None),
    "CrewAI": ("CrewAI Docs", "https://docs.crewai.com/", None),
    "MLflow": ("MLflow Docs", "https://mlflow.org/docs/latest/index.html", None),
    "spaCy": ("spaCy Usage", "https://spacy.io/usage", None),
    "NLTK": ("NLTK Docs", "https://www.nltk.org/", None),
    "OpenCV": ("OpenCV Docs", "https://docs.opencv.org/", None),
    "Whisper": ("Whisper Guide", "https://github.com/openai/whisper", None),
    "Stable Diffusion": ("Stable Diffusion Guide", "https://github.com/Stability-AI/stablediffusion", None),
    "YOLO": ("Ultralytics Docs", "https://docs.ultralytics.com/", None),
    "XGBoost": ("XGBoost Docs", "https://xgboost.readthedocs.io/", None),
    "LightGBM": ("LightGBM Docs", "https://lightgbm.readthedocs.io/", None),
    "NLP": ("NLTK Book", "https://www.nltk.org/book/", None),
    "Computer Vision": ("CS231n Notes", "https://cs231n.github.io/", None),
    "Deep Learning": ("Deep Learning Book", "https://www.deeplearningbook.org/", None),
    "Machine Learning": ("Google ML Crash Course", "https://developers.google.com/machine-learning/crash-course", None),
    "RAG": ("AWS RAG Guide", "https://aws.amazon.com/what-is/retrieval-augmented-generation/", None),
    "Prompt Engineering": ("Prompting Guide", "https://www.promptingguide.ai/", None),
    "Fine-tuning": ("OpenAI Fine-tuning", "https://platform.openai.com/docs/guides/fine-tuning", None),
    # ---- mobile ----
    "Flutter": ("Flutter Docs", "https://docs.flutter.dev/", None),
    "React Native": ("React Native Docs", "https://reactnative.dev/docs/getting-started", None),
    "Android": ("Android Docs", "https://developer.android.com/docs", None),
    "iOS": ("Apple iOS Docs", "https://developer.apple.com/ios/", None),
    "SwiftUI": ("SwiftUI Docs", "https://developer.apple.com/documentation/swiftui/", None),
    "Jetpack Compose": ("Compose Docs", "https://developer.android.com/jetpack/compose", None),
    "Ionic": ("Ionic Docs", "https://ionicframework.com/docs", None),
    "Xamarin": ("Xamarin Docs", "https://learn.microsoft.com/en-us/xamarin/", None),
    "Cordova": ("Cordova Docs", "https://cordova.apache.org/docs/", None),
    "Firebase": ("Firebase Docs", "https://firebase.google.com/docs", None),
    "Expo": ("Expo Docs", "https://docs.expo.dev/", None),
    "Fastlane": ("fastlane Docs", "https://docs.fastlane.tools/", None),
    # ---- testing ----
    "Jest": ("Jest Docs", "https://jestjs.io/docs/getting-started", None),
    "Mocha": ("Mocha Docs", "https://mochajs.org/", None),
    "Cypress": ("Cypress Docs", "https://docs.cypress.io/", None),
    "Playwright": ("Playwright Docs", "https://playwright.dev/docs/intro", None),
    "Selenium": ("Selenium Docs", "https://www.selenium.dev/documentation/", None),
    "Pytest": ("pytest Docs", "https://docs.pytest.org/", None),
    "JMeter": ("JMeter Manual", "https://jmeter.apache.org/usermanual/", None),
    "Gatling": ("Gatling Docs", "https://docs.gatling.io/", None),
    "k6": ("k6 Docs", "https://grafana.com/docs/k6/", None),
    "JUnit": ("JUnit Guide", "https://junit.org/junit5/docs/current/user-guide/", None),
    "Mockito": ("Mockito Site", "https://site.mockito.org/", None),
    "TestNG": ("TestNG Docs", "https://testng.org/", None),
    "React Testing Library": ("Testing Library Docs", "https://testing-library.com/docs/react-testing-library/intro/", None),
    "Postman": ("Postman Docs", "https://learning.postman.com/docs/introduction/overview/", None),
    # ---- tools ----
    "Git": ("Pro Git Book", "https://git-scm.com/book/en/v2", None),
    "GitHub": ("GitHub Docs", "https://docs.github.com/", None),
    "GitLab": ("GitLab Docs", "https://docs.gitlab.com/", None),
    "Bitbucket": ("Bitbucket Support", "https://support.atlassian.com/bitbucket/", None),
    "VS Code": ("VS Code Docs", "https://code.visualstudio.com/docs", None),
    "IntelliJ": ("IntelliJ Guide", "https://www.jetbrains.com/help/idea/getting-started.html", None),
    "Eclipse": ("Eclipse Help", "https://help.eclipse.org/latest/index.jsp", None),
    "Figma": ("Figma Help", "https://help.figma.com/hc/en-us", None),
    "Adobe XD": ("XD Guide", "https://helpx.adobe.com/xd/get-started.html", None),
    "Jira": ("Jira Guides", "https://www.atlassian.com/software/jira/guides", None),
    "Confluence": ("Confluence Guides", "https://www.atlassian.com/software/confluence/guides", None),
    "Trello": ("Trello Guide", "https://trello.com/guide", None),
    "Asana": ("Asana Guide", "https://asana.com/guide", None),
    "Notion": ("Notion Help", "https://www.notion.com/help", None),
    "Slack": ("Slack Help", "https://slack.com/help", None),
    "Miro": ("Miro Help", "https://help.miro.com/hc/en-us", None),
    "Linear": ("Linear Docs", "https://linear.app/docs", None),
    "Stripe": ("Stripe Docs", "https://docs.stripe.com/", None),
    "Twilio": ("Twilio Docs", "https://www.twilio.com/docs", None),
    "Auth0": ("Auth0 Docs", "https://auth0.com/docs", None),
    "Keycloak": ("Keycloak Docs", "https://www.keycloak.org/documentation", None),
    "JWT": ("JWT Introduction", "https://jwt.io/introduction", None),
    "OAuth": ("OAuth 2.0 Guide", "https://oauth.net/2/", None),
    "SAML": ("Auth0 SAML Guide", "https://auth0.com/docs/authenticate/protocols/saml", None),
    "Docker Compose": ("Compose Docs", "https://docs.docker.com/compose/", None),
    "JSON": ("JSON Docs", "https://www.json.org/json-en.html", None),
    "XML": ("W3C XML", "https://www.w3.org/XML/", None),
    "YAML": ("YAML Spec", "https://yaml.org/spec/1.2.2/", None),
    "WebRTC": ("WebRTC Guide", "https://webrtc.org/getting-started/overview", None),
    "Agile": ("Atlassian Agile Guide", "https://www.atlassian.com/agile", None),
    "Scrum": ("Atlassian Scrum Guide", "https://www.atlassian.com/agile/scrum", None),
    "Kanban": ("Atlassian Kanban Guide", "https://www.atlassian.com/agile/kanban", None),
    # ---- security ----
    "OWASP": ("OWASP Top Ten", "https://owasp.org/www-project-top-ten/", None),
    "Wireshark": ("Wireshark Docs", "https://www.wireshark.org/docs/", None),
    "Nmap": ("Nmap Docs", "https://nmap.org/docs.html", None),
    "Burp Suite": ("Burp Docs", "https://portswigger.net/burp/documentation", None),
    "Metasploit": ("Metasploit Docs", "https://docs.metasploit.com/", None),
    "Nessus": ("Nessus Docs", "https://docs.tenable.com/nessus", None),
    "Kali Linux": ("Kali Docs", "https://www.kali.org/docs/", None),
    "Cryptography": ("Cryptopals Challenges", "https://cryptopals.com/", None),
    "Penetration Testing": ("OWASP Testing Guide", "https://owasp.org/www-project-web-security-testing-guide/", None),
    "Zero Trust": ("NIST SP 800-207", "https://csrc.nist.gov/pubs/sp/800/207/final", None),
    "SIEM": ("Splunk SIEM Guide", "https://www.splunk.com/en_us/blog/learn/siem-security-information-event-management.html", None),
    # ---- fundamentals ----
    "Algorithms": ("VisuAlgo", "https://visualgo.net/en", None),
    "Data Structures": ("VisuAlgo", "https://visualgo.net/en", None),
    "OOP": ("Java OOP Tutorial", "https://docs.oracle.com/javase/tutorial/java/concepts/", None),
    "SOLID Principles": ("SOLID Guide (DO)", "https://www.digitalocean.com/community/conceptual-articles/s-o-l-i-d-the-first-five-principles-of-object-oriented-design", None),
    "Design Patterns": ("Refactoring Guru", "https://refactoring.guru/design-patterns", None),
    "DBMS": ("GFG DBMS Tutorial", "https://www.geeksforgeeks.org/dbms/dbms", None),
    "Operating Systems": ("OSTEP Book", "https://pages.cs.wisc.edu/~remzi/OSTEP/", None),
    "Computer Networks": ("GFG Networks", "https://www.geeksforgeeks.org/computer-network-tutorials/", None),
    "Distributed Systems": ("MIT 6.824", "https://pdos.csail.mit.edu/6.824/", None),
    "System Design": ("System Design Primer", "https://github.com/donnemartin/system-design-primer", None),
}


def canonical_skills() -> list[str]:
    with open(SKILL_TAXONOMY_CSV, newline="", encoding="utf-8") as fh:
        names = set()
        for row in csv.DictReader(fh):
            if not (row.get("alias_of") or "").strip() and (row.get("name") or "").strip():
                names.add(row["name"].strip())
    return sorted(names)


def yt_url(skill: str, qualifier: str | None) -> str:
    query = f"{skill} full course" + (f" {qualifier}" if qualifier else "")
    return YT + quote_plus(query)


def main() -> int:
    skills = canonical_skills()
    missing = [s for s in skills if s not in DOCS]
    if missing:
        print(f"MISSING docs for {len(missing)} skills:")
        for s in missing:
            print(f"  - {s}")
        return 1
    extra = [s for s in DOCS if s not in skills]
    if extra:
        print(f"NOTE: {len(extra)} mapped skills not in taxonomy (typo?): {extra}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["skill", "title", "url_documentation", "url_youtube"])
        for skill in skills:
            title, docs_url, qualifier = DOCS[skill]
            writer.writerow([skill, title, docs_url, yt_url(skill, qualifier)])
    print(f"wrote {len(skills)} rows -> {OUT}")
    return 0


if __name__ == "__main__":
    main() if "--check-only" not in sys.argv else (
        print("\n".join(s for s in canonical_skills() if s not in DOCS)) or print("FULL COVERAGE")
    )
