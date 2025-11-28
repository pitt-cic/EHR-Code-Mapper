#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import {CodeMappingStack} from '../lib/code-mapping-stack';

const app = new cdk.App();
new CodeMappingStack(app, 'CodeMappingStack', {
    env: {
        account: process.env.CDK_DEFAULT_ACCOUNT,
        region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
    }
});