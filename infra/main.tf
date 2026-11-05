# Archon Treasury demo as deployed: one Lambda plus a public Function URL.
# This file mirrors the live resources created 2026-11-04 (Lambda
# archon-treasury-demo, eu-west-1) so a fresh account can reproduce them:
#   python scripts/package_lambda.py
#   terraform init && terraform apply -var deployed_sha=zip-<sha256 from that script>
# The App Runner variant was replaced on 2026-11-05 to match reality (G1:
# docs, code, and deployment must agree). Teardown: terraform destroy.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "deployed_sha" {
  type        = string
  description = "Artifact provenance served at /DEPLOYED_SHA (zip SHA-256 until a git SHA exists)"
}

variable "zip_path" {
  type    = string
  default = "../temp/archon-lambda.zip"
}

provider "aws" {
  region = var.aws_region
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "archon-treasury-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "demo" {
  function_name    = "archon-treasury-demo"
  runtime          = "python3.12"
  handler          = "archon_demo.lambda_handler.handler"
  role             = aws_iam_role.lambda.arn
  filename         = var.zip_path
  source_code_hash = filebase64sha256(var.zip_path)
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      DEPLOYED_SHA = var.deployed_sha
    }
  }
}

resource "aws_lambda_function_url" "demo" {
  function_name      = aws_lambda_function.demo.function_name
  authorization_type = "NONE"
}

# Both permissions are required for anonymous access (Trap T5).
resource "aws_lambda_permission" "url_public" {
  statement_id           = "FunctionURLAllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.demo.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "url_invoke" {
  statement_id             = "FunctionURLAllowPublicInvoke"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.demo.function_name
  principal                = "*"
  invoked_via_function_url = true
}

output "demo_url" {
  value = aws_lambda_function_url.demo.function_url
}
